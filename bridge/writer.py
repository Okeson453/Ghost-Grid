"""
bridge/writer.py
Async pipe writer with enterprise-grade queue management.

The writer maintains a queue of outbound messages and drains them asynchronously
to the pipe. This decouples the scoring pipeline (enqueue) from pipe write latency.

Features:
- Bounded queue with overflow tracking (prevents memory leaks)
- Metrics for queue depth and write performance
- Graceful degradation when pipe is slow
- Circuit breaker pattern for write failures
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipe_client import PipeClient


log = logging.getLogger(__name__)


class WriterMetrics:
    """Metrics for pipe writer health and performance."""
    def __init__(self) -> None:
        self.total_enqueued: int = 0
        self.total_written: int = 0
        self.write_failures: int = 0
        self.queue_overflows: int = 0
        self.max_queue_depth: int = 0
        self.avg_queue_depth: float = 0.0
        self.last_write_ts: float = 0.0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_enqueued = 0
        self.total_written = 0
        self.write_failures = 0
        self.queue_overflows = 0
        self.max_queue_depth = 0
        self.avg_queue_depth = 0.0


class PipeWriter:
    """Async queue-based pipe writer with enterprise features."""

    def __init__(self, pipe_client: PipeClient, queue_maxsize: int = 200) -> None:
        self._pipe = pipe_client
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_maxsize)
        self._metrics = WriterMetrics()
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_open = False

    @property
    def metrics(self) -> WriterMetrics:
        """Get writer metrics for monitoring."""
        return self._metrics

    def enqueue(self, message: str) -> bool:
        """
        Enqueue a message for writing. Non-blocking.
        Returns True if enqueued, False if queue full.
        
        Logs warning if queue is full (drops oldest message via overflow).
        """
        # Check circuit breaker
        if self._circuit_breaker_open:
            log.warning("Circuit breaker open, dropping message")
            return False
        
        try:
            self._queue.put_nowait(message)
            self._metrics.total_enqueued += 1
            
            # Track max queue depth
            current_depth = self._queue.qsize()
            if current_depth > self._metrics.max_queue_depth:
                self._metrics.max_queue_depth = current_depth
            
            return True
        except asyncio.QueueFull:
            self._metrics.queue_overflows += 1
            log.warning(f"Write queue full (size={self._queue.qsize()}) "
                       f"— dropping message: {message[:50]}...")
            # Try to drop oldest and enqueue new one
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(message)
                self._metrics.total_enqueued += 1
                return True
            except asyncio.QueueEmpty:
                return False

    async def run(self) -> None:
        """
        Drain queue and write messages to pipe.
        Logs failures without crashing.

        WHY separate queue: Decouples scoring pipeline (which calls enqueue)
        from pipe write latency. Scoring remains responsive even if MT5 is slow
        to read from pipe. Queue bounded to prevent memory leak.
        """
        while True:
            try:
                # Check circuit breaker - reset after cooldown
                if self._circuit_breaker_open:
                    log.info("Circuit breaker cooling down...")
                    await asyncio.sleep(5.0)
                    self._circuit_breaker_open = False
                    self._circuit_breaker_failures = 0
                    log.info("Circuit breaker reset")
                    continue

                # Wait for message in queue with timeout
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Queue empty — continue loop
                    continue

                # Write to pipe
                ok = await self._pipe.writeline(message)
                if ok:
                    self._metrics.total_written += 1
                    self._metrics.last_write_ts = time.time()
                    self._circuit_breaker_failures = 0  # Reset on success
                else:
                    self._metrics.write_failures += 1
                    self._circuit_breaker_failures += 1
                    
                    # Check if should open circuit breaker
                    if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                        log.critical(
                            f"Write failures exceeded threshold "
                            f"({self._circuit_breaker_failures}) — opening circuit breaker"
                        )
                        self._circuit_breaker_open = True
                    else:
                        log.warning(
                            f"Failed to write: {message[:50]}... "
                            f"(failures: {self._circuit_breaker_failures}/{self._circuit_breaker_threshold})"
                        )

            except asyncio.CancelledError:
                log.info("Writer cancelled")
                raise
            except Exception as e:
                log.error(f"Writer error: {e}")
                self._metrics.write_failures += 1
                await asyncio.sleep(0.1)  # Backoff

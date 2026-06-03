"""
bridge/reader.py
Async pipe reader with enterprise-grade message dispatch.

Reads lines from MT5 pipe, parses messages, and dispatches them to appropriate
queues or handlers (per-symbol tick queues, fill queue, etc.).

Features:
- Per-symbol tick queue management (lazy creation)
- Message dispatch with metrics tracking
- Drop-oldest overflow handling for high-frequency ticks
- Comprehensive health monitoring
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from .protocol import parse_inbound, InboundType, TickMessage

if TYPE_CHECKING:
    from .pipe_client import PipeClient


log = logging.getLogger(__name__)


class ReaderMetrics:
    """Metrics for pipe reader health and performance."""
    def __init__(self) -> None:
        self.total_lines_read: int = 0
        self.messages_dispatched: int = 0
        self.dispatch_errors: int = 0
        self.ticks_dispatched: int = 0
        self.fills_dispatched: int = 0
        self.rejects_dispatched: int = 0
        self.closed_dispatched: int = 0
        self.heartbeats_dispatched: int = 0
        self.tick_queue_overflows: int = 0
        self.fill_queue_overflows: int = 0
        self.last_read_ts: float = 0.0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_lines_read = 0
        self.messages_dispatched = 0
        self.dispatch_errors = 0
        self.ticks_dispatched = 0
        self.fills_dispatched = 0
        self.rejects_dispatched = 0
        self.closed_dispatched = 0
        self.heartbeats_dispatched = 0
        self.tick_queue_overflows = 0
        self.fill_queue_overflows = 0


class PipeReader:
    """Async pipe reader with message dispatch and metrics."""

    def __init__(self, pipe_client: PipeClient) -> None:
        self._pipe = pipe_client
        self._tick_queues: dict[str, asyncio.Queue] = {}
        self._fill_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.last_heartbeat_ts: float = time.time()
        self._metrics = ReaderMetrics()

    @property
    def metrics(self) -> ReaderMetrics:
        """Get reader metrics for monitoring."""
        return self._metrics

    def get_tick_queue(self, symbol: str) -> asyncio.Queue[TickMessage]:
        """Lazy-create per-symbol tick queue (maxsize=50)."""
        if symbol not in self._tick_queues:
            self._tick_queues[symbol] = asyncio.Queue(maxsize=50)
            log.debug(f"Created tick queue for {symbol}")
        return self._tick_queues[symbol]

    async def run(self) -> None:
        """
        Async read loop: read lines, parse, dispatch.
        Runs forever (until cancelled).
        """
        while True:
            try:
                # Read one line from pipe
                line = await self._pipe.readline()
                if line is None:
                    # Connection lost or no data
                    await asyncio.sleep(0.1)
                    continue

                self._metrics.total_lines_read += 1
                self._metrics.last_read_ts = time.time()

                # Parse message
                msg = parse_inbound(line)
                if msg is None:
                    log.debug(f"Unparseable message: {line[:100]}")
                    continue

                # Dispatch
                try:
                    self._dispatch(msg)
                    self._metrics.messages_dispatched += 1
                except Exception as e:
                    self._metrics.dispatch_errors += 1
                    log.error(f"Dispatch error: {e}")

            except asyncio.CancelledError:
                log.info("Reader cancelled")
                raise
            except Exception as e:
                log.error(f"Reader error: {e}")
                await asyncio.sleep(0.1)

    def _dispatch(self, msg) -> None:
        """Route message to appropriate queue or handler."""
        if isinstance(msg, TickMessage):
            # Route to per-symbol tick queue
            queue = self.get_tick_queue(msg.symbol)
            try:
                queue.put_nowait(msg)
                self._metrics.ticks_dispatched += 1
            except asyncio.QueueFull:
                # Drop oldest tick (not block)
                self._metrics.tick_queue_overflows += 1
                try:
                    queue.get_nowait()
                    queue.put_nowait(msg)
                    self._metrics.ticks_dispatched += 1
                except asyncio.QueueEmpty:
                    log.warning(f"Failed to drop tick from {msg.symbol} queue")

        elif msg.__class__.__name__ in ("FillMessage", "RejectMessage", "ClosedMessage"):
            # Route to fill queue
            try:
                self._fill_queue.put_nowait(msg)
                msg_type = msg.__class__.__name__
                if msg_type == "FillMessage":
                    self._metrics.fills_dispatched += 1
                elif msg_type == "RejectMessage":
                    self._metrics.rejects_dispatched += 1
                elif msg_type == "ClosedMessage":
                    self._metrics.closed_dispatched += 1
            except asyncio.QueueFull:
                self._metrics.fill_queue_overflows += 1
                log.warning(f"Fill queue full — message dropped: {msg.__class__.__name__}")

        elif msg.__class__.__name__ == "HeartbeatMessage":
            # Update heartbeat timestamp
            self.last_heartbeat_ts = time.time()
            self._metrics.heartbeats_dispatched += 1
            log.debug(f"Heartbeat from MT5 (ts={msg.timestamp_ms})")

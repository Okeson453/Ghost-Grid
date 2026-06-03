"""
bridge/writer.py
Async pipe writer with queue-based decoupling.

The writer maintains a queue of outbound messages and drains them asynchronously
to the pipe. This decouples the scoring pipeline (enqueue) from pipe write latency.
"""

from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipe_client import PipeClient


log = logging.getLogger(__name__)


class PipeWriter:
    """Async queue-based pipe writer."""

    def __init__(self, pipe_client: PipeClient) -> None:
        self._pipe = pipe_client
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    def enqueue(self, message: str) -> None:
        """
        Enqueue a message for writing. Non-blocking.
        Logs warning if queue is full (drops oldest message).
        """
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            log.warning(f"Write queue full — message dropped: {message[:50]}")

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
                # Wait for message in queue
                message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                # Write to pipe
                ok = await self._pipe.writeline(message)
                if not ok:
                    log.warning(f"Failed to write: {message[:50]}")
            except asyncio.TimeoutError:
                # Queue empty — continue loop
                continue
            except Exception as e:
                log.error(f"Writer error: {e}")
                await asyncio.sleep(0.1)  # Backoff

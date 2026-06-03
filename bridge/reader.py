"""
bridge/reader.py
Async pipe reader with message dispatch.

Reads lines from MT5 pipe, parses messages, and dispatches them to appropriate
queues or handlers (per-symbol tick queues, fill queue, etc.).
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


class PipeReader:
    """Async pipe reader with message dispatch."""

    def __init__(self, pipe_client: PipeClient) -> None:
        self._pipe = pipe_client
        self._tick_queues: dict[str, asyncio.Queue] = {}
        self._fill_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.last_heartbeat_ts: float = time.time()

    def get_tick_queue(self, symbol: str) -> asyncio.Queue[TickMessage]:
        """Lazy-create per-symbol tick queue."""
        if symbol not in self._tick_queues:
            self._tick_queues[symbol] = asyncio.Queue(maxsize=50)
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
                    # Connection lost
                    await asyncio.sleep(0.1)
                    continue

                # Parse message
                msg = parse_inbound(line)
                if msg is None:
                    log.debug(f"Unparseable message: {line[:100]}")
                    continue

                # Dispatch
                self._dispatch(msg)

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
            except asyncio.QueueFull:
                # Drop oldest tick (not block)
                try:
                    queue.get_nowait()
                    queue.put_nowait(msg)
                except asyncio.QueueEmpty:
                    pass

        elif msg.__class__.__name__ in ("FillMessage", "RejectMessage", "ClosedMessage"):
            # Route to fill queue
            try:
                self._fill_queue.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning(f"Fill queue full — message dropped: {msg}")

        elif msg.__class__.__name__ == "HeartbeatMessage":
            # Update heartbeat timestamp
            self.last_heartbeat_ts = time.time()
            log.debug(f"Heartbeat from MT5")

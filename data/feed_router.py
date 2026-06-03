"""
data/feed_router.py
Per-symbol tick routing to concurrent asyncio tasks.

FeedRouter launches one independent task per trading symbol. Each task
drains its tick queue and feeds ticks to a SnapshotBuilder. This design
ensures that a slow symbol (e.g., heavy computation) does not delay others.

WHY per-symbol tasks: Concurrent processing allows real-time responsiveness.
If symbol A has compute-heavy regime detection, symbol B's ticks are still
processed immediately. Tasks communicate via asyncio.Queue (non-blocking).
"""

from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable, Optional, TYPE_CHECKING

from config import INSTRUMENTS
from .schema import MarketSnapshot
from .snapshot_builder import SnapshotBuilder

if TYPE_CHECKING:
    from bridge import PipeReader


log = logging.getLogger(__name__)

# Type alias for snapshot callback
ScoringCallback = Callable[[MarketSnapshot], Awaitable[None]]


class FeedRouter:
    """Routes ticks to per-symbol tasks."""

    def __init__(
        self,
        pipe_reader: PipeReader,
        on_snapshot: ScoringCallback,
    ) -> None:
        self._reader = pipe_reader
        self._on_snapshot = on_snapshot
        # Pre-create builders and tick queues for all instruments
        self._builders = {symbol: SnapshotBuilder(symbol) for symbol in INSTRUMENTS}
        # Pre-register all symbol queues with reader
        for symbol in INSTRUMENTS:
            self._reader.get_tick_queue(symbol)

    async def run(self) -> None:
        """Launch per-symbol processing tasks."""
        tasks = [
            asyncio.create_task(self._symbol_loop(symbol)) for symbol in INSTRUMENTS
        ]
        # Wait for all tasks (should run forever until cancelled)
        await asyncio.gather(*tasks)

    async def _symbol_loop(self, symbol: str) -> None:
        """
        Drain tick queue for one symbol.
        Feed ticks to SnapshotBuilder, emit snapshots via callback.
        Never crashes — catches exceptions per-tick.
        """
        builder = self._builders[symbol]
        queue = self._reader.get_tick_queue(symbol)

        while True:
            try:
                # Wait for next tick
                tick = await queue.get()

                # Build snapshot
                snapshot = builder.on_tick(tick)
                if snapshot is not None:
                    # Emit to scoring layer
                    try:
                        await self._on_snapshot(snapshot)
                    except Exception as e:
                        log.error(f"Snapshot callback error ({symbol}): {e}")

            except asyncio.CancelledError:
                # Task cancelled — exit gracefully
                log.info(f"Symbol loop cancelled: {symbol}")
                raise
            except Exception as e:
                log.error(f"Symbol loop error ({symbol}): {e}")
                await asyncio.sleep(0.1)  # Backoff on repeated errors

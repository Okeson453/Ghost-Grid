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


class FeedRouterMetrics:
    """Metrics for feed router."""
    def __init__(self) -> None:
        self.total_snapshots: int = 0
        self.callback_errors: int = 0
        self.symbols_processed: int = 0
        self.per_symbol_counts: dict[str, int] = {}  # Snapshot count per symbol

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_snapshots = 0
        self.callback_errors = 0
        self.symbols_processed = 0
        self.per_symbol_counts.clear()


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
        self._metrics = FeedRouterMetrics()
        # Initialize per-symbol counters
        for symbol in INSTRUMENTS:
            self._metrics.per_symbol_counts[symbol] = 0

    @property
    def metrics(self) -> FeedRouterMetrics:
        """Get feed router metrics."""
        return self._metrics

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
                    self._metrics.total_snapshots += 1
                    self._metrics.per_symbol_counts[symbol] += 1
                    # Emit to scoring layer
                    try:
                        await self._on_snapshot(snapshot)
                    except Exception as e:
                        self._metrics.callback_errors += 1
                        log.error(f"Snapshot callback error ({symbol}): {e}")

            except asyncio.CancelledError:
                # Task cancelled — exit gracefully
                log.info(f"Symbol loop cancelled: {symbol}")
                raise
            except Exception as e:
                log.error(f"Symbol loop error ({symbol}): {e}")
                await asyncio.sleep(0.1)  # Backoff on repeated errors

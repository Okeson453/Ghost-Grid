"""
data/aggregator.py
OHLCV bar aggregator (M1, M3, M5).

Builds OHLCV bars from tick data. Supports multiple timeframes concurrently.
Uses time-based bar boundaries: bar open_ts is snapped to the nearest
bar-period-aligned boundary (e.g., 0:00:00, 0:01:00, 0:03:00, 0:05:00).
"""

from __future__ import annotations
from dataclasses import dataclass

from .schema import Tick, OHLCV, BarBuffer


# Timeframe durations in milliseconds
TIMEFRAME_MS = {
    "M1": 60 * 1000,
    "M3": 3 * 60 * 1000,
    "M5": 5 * 60 * 1000,
}


class _OpenBar:
    """Private in-progress bar (mutable)."""

    __slots__ = ("symbol", "timeframe", "open_ts", "open", "high", "low", "close", "volume")

    def __init__(self, symbol: str, timeframe: str, tick: Tick) -> None:
        bar_dur_ms = TIMEFRAME_MS[timeframe]
        # Snap open_ts to bar boundary: (ts // dur) * dur
        self.open_ts = (tick.timestamp_ms // bar_dur_ms) * bar_dur_ms
        self.symbol = symbol
        self.timeframe = timeframe
        mid = tick.mid
        self.open = mid
        self.high = mid
        self.low = mid
        self.close = mid
        self.volume = 0

    def update(self, tick: Tick) -> None:
        """Update bar with new tick."""
        mid = tick.mid
        self.high = max(self.high, mid)
        self.low = min(self.low, mid)
        self.close = mid
        self.volume += tick.tick_volume

    def should_close(self, tick_ts_ms: int) -> bool:
        """Check if tick crosses into next bar period."""
        bar_dur_ms = TIMEFRAME_MS[self.timeframe]
        tick_bar_ts = (tick_ts_ms // bar_dur_ms) * bar_dur_ms
        return tick_bar_ts > self.open_ts

    def to_ohlcv(self) -> OHLCV:
        """Return frozen OHLCV bar."""
        return OHLCV(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            timestamp_ms=self.open_ts,
        )


class OHLCVAggregator:
    """Aggregates ticks into M1/M3/M5 OHLCV bars."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._open_bars: dict[str, _OpenBar | None] = {
            "M1": None,
            "M3": None,
            "M5": None,
        }
        self._buffers = {
            "M1": BarBuffer(symbol=symbol, timeframe="M1", max_size=300),
            "M3": BarBuffer(symbol=symbol, timeframe="M3", max_size=200),
            "M5": BarBuffer(symbol=symbol, timeframe="M5", max_size=100),
        }

    def on_tick(self, tick: Tick) -> list[OHLCV]:
        """
        Process one tick. Returns list of newly completed bars (0-3 items).

        WHY time-based boundaries: (ts // bar_dur_ms) * bar_dur_ms ensures
        consistent bar alignment across all symbols and sessions, independent
        of tick arrival timing. Prevents micro-gaps or overlaps in bar timing.
        """
        completed_bars: list[OHLCV] = []

        for timeframe in ["M1", "M3", "M5"]:
            bar = self._open_bars[timeframe]

            if bar is None:
                # Create new bar
                self._open_bars[timeframe] = _OpenBar(self.symbol, timeframe, tick)
            elif bar.should_close(tick.timestamp_ms):
                # Close current bar and start new one
                completed_bars.append(bar.to_ohlcv())
                self._buffers[timeframe].append(bar.to_ohlcv())
                self._open_bars[timeframe] = _OpenBar(self.symbol, timeframe, tick)
            else:
                # Update current bar
                bar.update(tick)

        return completed_bars

    @property
    def buffers(self) -> dict[str, BarBuffer]:
        """Access read-only bar buffers."""
        return self._buffers

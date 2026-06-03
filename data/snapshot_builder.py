"""
data/snapshot_builder.py
Assembles complete MarketSnapshot objects from tick data.

The SnapshotBuilder orchestrates multiple calculations:
- OHLCV aggregation (M1/M3/M5 bars)
- CVD accumulation with session boundaries
- VWAP with session reset
- ATR (Wilder's) for volatility estimation

Returns None until the buffer has warmed up (20 M1 bars, 14 M5 bars).
"""

from __future__ import annotations
from typing import Optional

from config import get_current_session
from .schema import Tick, MarketSnapshot
from .aggregator import OHLCVAggregator
from .cvd_engine import CVDEngine
from .vwap import VWAPCalculator
from .atr import ATRCalculator


class SnapshotBuilder:
    """Builds complete MarketSnapshot objects from tick data."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._agg = OHLCVAggregator(symbol)
        self._cvd = CVDEngine(symbol)
        self._vwap = VWAPCalculator()
        self._atr_1m = ATRCalculator(period=14)
        self._atr_5m = ATRCalculator(period=14)
        self._current_session = ""

    def on_tick(self, tick: Tick) -> Optional[MarketSnapshot]:
        """
        Process one tick and return MarketSnapshot if ready, else None.

        Steps:
        1. Detect current session
        2. Aggregate tick into M1/M3/M5 bars
        3. Update VWAP with tick
        4. On M1 bar close: update CVD and ATR_1m
        5. On M5 bar close: update ATR_5m
        6. Guard: return None if buffers not warm
        7. Return complete MarketSnapshot (regime="" for now)
        """
        self._current_session = get_current_session()

        # Run aggregator — returns newly completed bars
        new_bars = self._agg.on_tick(tick)

        # Update VWAP with every tick
        self._vwap.update(tick)

        # On M1 bar close: update CVD and ATR_1m
        m1_bars = new_bars
        if m1_bars and [b for b in m1_bars if b.timeframe == "M1"]:
            m1_bar = [b for b in m1_bars if b.timeframe == "M1"][0]
            # CVD updated on M1 close (actual CVD calculation happens in regime layer)
            # For now, use 0.0 as placeholder (will be filled by regime/cvd module)
            self._cvd.on_bar_close(0.0, self._current_session)
            self._atr_1m.update(m1_bar)

        # On M5 bar close: update ATR_5m
        if m1_bars and [b for b in m1_bars if b.timeframe == "M5"]:
            m5_bar = [b for b in m1_bars if b.timeframe == "M5"][0]
            self._atr_5m.update(m5_bar)

        # Guard: return None if not warmed up
        m1_count = len(self._agg._buffers["M1"])
        m5_count = len(self._agg._buffers["M5"])
        if m1_count < 20 or m5_count < 14:
            return None

        # Build and return MarketSnapshot
        return MarketSnapshot(
            symbol=self.symbol,
            tick=tick,
            m1=self._agg._buffers["M1"].latest,
            m3=self._agg._buffers["M3"].latest,
            m5=self._agg._buffers["M5"].latest,
            cvd_history=self._cvd.history(),
            vwap=self._vwap.value,
            atr_1m=self._atr_1m.value,
            atr_5m=self._atr_5m.value,
            session=self._current_session,
            regime="",  # Empty until Part 3 (regime detection) is merged
        )

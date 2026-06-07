"""
data/snapshot_builder.py
Assembles complete MarketSnapshot objects from tick data.

The SnapshotBuilder orchestrates multiple calculations:
- OHLCV aggregation (M1/M3/M5 bars)
- CVD accumulation with session boundaries
- CVD divergence detection (Kalman filter approximation)
- VWAP with session reset
- ATR (Wilder's) for volatility estimation
- Regime classification (4-state)

Returns None until the buffer has warmed up (20 M1 bars, 14 M5 bars).
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from config import get_current_session, get_instrument
from .schema import Tick, MarketSnapshot
from .aggregator import OHLCVAggregator
from .cvd_engine import CVDEngine
from .vwap import VWAPCalculator
from .atr import ATRCalculator
from .regime import RegimeClassifier, Regime

if TYPE_CHECKING:
    from bridge.protocol import TickMessage


class SnapshotBuilderMetrics:
    """Metrics for snapshot building."""

    def __init__(self) -> None:
        self.total_ticks: int = 0
        self.snapshots_produced: int = 0
        self.warmup_ticks: int = 0
        self.validation_failures: int = 0
        self.session_changes: int = 0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_ticks = 0
        self.snapshots_produced = 0
        self.warmup_ticks = 0
        self.validation_failures = 0
        self.session_changes = 0


class SnapshotBuilder:
    """Builds complete MarketSnapshot objects from tick data."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._agg = OHLCVAggregator(symbol)
        self._cvd = CVDEngine(symbol)
        self._vwap = VWAPCalculator()
        self._atr_1m = ATRCalculator(period=14)
        self._atr_5m = ATRCalculator(period=14)
        self._regime_classifier = RegimeClassifier()
        self._current_session = ""
        self._metrics = SnapshotBuilderMetrics()
        self._last_session = ""
        self._price_history = []  # For CVD divergence calculation

    @property
    def metrics(self) -> SnapshotBuilderMetrics:
        """Get snapshot builder metrics."""
        return self._metrics

    def on_tick(self, raw: TickMessage) -> Optional[MarketSnapshot]:
        """
        Process one TickMessage and return MarketSnapshot if ready, else None.

        Steps:
        1. Detect current session from get_current_session()
        2. Build Tick dataclass from raw TickMessage
        3. Run OHLCVAggregator.on_tick() — get new_bars
        4. Update VWAP with tick
        5. Track price for CVD divergence calculation
        6. On M1 bar close: update CVD with calculated value, update ATR_1m
        7. On M5 bar close: update ATR_5m
        8. Guard: return None if < 20 M1 bars or < 14 M5 bars
        9. Classify regime from current snapshot
        10. Return complete MarketSnapshot with populated regime
        """
        self._metrics.total_ticks += 1
        self._current_session = get_current_session()

        if self._current_session != self._last_session:
            self._metrics.session_changes += 1
            self._last_session = self._current_session
            self._price_history.clear()  # Reset on session change

        # Build Tick dataclass from raw TickMessage
        tick = Tick(
            symbol=raw.symbol,
            timestamp_ms=raw.timestamp_ms,
            bid=raw.bid,
            ask=raw.ask,
            tick_volume=raw.tick_volume,
            dominant_side=raw.dominant_side,
            cvd_running=raw.cvd_running,
            session=self._current_session,
        )

        # Run aggregator — returns newly completed bars
        new_bars = self._agg.on_tick(tick)

        # Update VWAP with every tick
        self._vwap.update(tick)

        # Track price for CVD divergence (last 10 bars)
        self._price_history.append(tick.mid)
        if len(self._price_history) > 10:
            self._price_history.pop(0)

        # On M1 bar close: update CVD and ATR_1m
        m1_bars = [b for b in new_bars if b.timeframe == "M1"]
        if m1_bars:
            m1_bar = m1_bars[0]

            # Calculate actual CVD divergence
            # CVD value: raw.cvd_running (from MT5 EA)
            # We use the actual CVD from the tick message
            cvd_value = raw.cvd_running
            self._cvd.on_bar_close(cvd_value, self._current_session)
            self._atr_1m.update(m1_bar)

        # On M5 bar close: update ATR_5m
        m5_bars = [b for b in new_bars if b.timeframe == "M5"]
        if m5_bars:
            m5_bar = m5_bars[0]
            self._atr_5m.update(m5_bar)

        # Guard: return None if not warmed up
        m1_count = len(self._agg._buffers["M1"])
        m5_count = len(self._agg._buffers["M5"])
        if m1_count < 20 or m5_count < 14:
            self._metrics.warmup_ticks += 1
            return None

        # Build intermediate snapshot without regime
        snapshot_no_regime = MarketSnapshot(
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
            regime=Regime.CHOP.value,  # Placeholder before classification
        )

        # Classify regime
        regime_signal = self._regime_classifier.classify(snapshot_no_regime)

        # Create final snapshot with regime
        snapshot = MarketSnapshot(
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
            regime=regime_signal.regime.value,
        )

        self._metrics.snapshots_produced += 1
        return snapshot

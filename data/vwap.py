"""
data/vwap.py
Session-reset VWAP calculator.

VWAP (Volume-Weighted Average Price) tracks the cumulative average price
weighted by volume. The key feature: VWAP resets to 0.0 when the trading
session changes.

WHY session reset: Different trading sessions have different price levels.
Asian VWAP, London VWAP, and NY VWAP are independent — using a continuous
VWAP across session boundaries contaminates the calculation. Session reset
forces VWAP to recompute from the first tick of each session.
"""

from __future__ import annotations

from .schema import Tick


class VWAPMetrics:
    """Metrics for VWAP calculation."""
    def __init__(self) -> None:
        self.total_ticks: int = 0
        self.session_resets: int = 0
        self.zero_volume_skips: int = 0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_ticks = 0
        self.session_resets = 0
        self.zero_volume_skips = 0


class VWAPCalculator:
    """VWAP calculator with session-boundary reset."""

    def __init__(self) -> None:
        self._cum_tp_volume: float = 0.0  # cumulative (typical_price * volume)
        self._cum_volume: float = 0.0      # cumulative volume
        self._last_session: str | None = None
        self._metrics = VWAPMetrics()

    @property
    def metrics(self) -> VWAPMetrics:
        """Get VWAP metrics."""
        return self._metrics

    def update(self, tick: Tick) -> None:
        """
        Update VWAP with a new tick.
        Resets cumulative values if session changes.
        """
        self._metrics.total_ticks += 1
        
        if tick.session != self._last_session:
            # Session boundary crossed — reset
            self._cum_tp_volume = 0.0
            self._cum_volume = 0.0
            self._last_session = tick.session
            self._metrics.session_resets += 1

        # Accumulate
        if tick.tick_volume == 0:
            self._metrics.zero_volume_skips += 1
            return
        
        typical_price = (tick.bid + tick.ask + tick.mid) / 3.0
        self._cum_tp_volume += typical_price * tick.tick_volume
        self._cum_volume += tick.tick_volume

    @property
    def value(self) -> float:
        """Return current VWAP (0.0 if no data)."""
        if self._cum_volume == 0.0:
            return 0.0
        return self._cum_tp_volume / self._cum_volume

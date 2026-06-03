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


class VWAPCalculator:
    """VWAP calculator with session-boundary reset."""

    def __init__(self) -> None:
        self._cum_tp_volume: float = 0.0  # cumulative (typical_price * volume)
        self._cum_volume: float = 0.0      # cumulative volume
        self._last_session: str | None = None

    def update(self, tick: Tick) -> None:
        """
        Update VWAP with a new tick.
        Resets cumulative values if session changes.
        """
        if tick.session != self._last_session:
            # Session boundary crossed — reset
            self._cum_tp_volume = 0.0
            self._cum_volume = 0.0
            self._last_session = tick.session

        # Accumulate
        typical_price = (tick.bid + tick.ask + tick.mid) / 3.0
        self._cum_tp_volume += typical_price * tick.tick_volume
        self._cum_volume += tick.tick_volume

    @property
    def value(self) -> float:
        """Return current VWAP (0.0 if no data)."""
        if self._cum_volume == 0.0:
            return 0.0
        return self._cum_tp_volume / self._cum_volume

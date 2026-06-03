"""
data/atr.py
Wilder's smoothed ATR calculator.

Wilder's ATR uses exponential smoothing (alpha = 1/period) on the true range,
initialised with a simple average of the first N true ranges. This is more
responsive to volatility changes than a simple moving average.

WHY Wilder's smoothing vs EMA: Wilder's method gives slightly more weight to
recent true ranges while still dampening spike noise. For a 14-bar ATR, alpha=1/14
means each new TR contributes ~7% to the smoothed value, providing stability
without excessive lag.
"""

from __future__ import annotations
from dataclasses import dataclass

from .schema import OHLCV


@dataclass
class ATRCalculator:
    """Wilder's smoothed ATR calculator."""

    period: int = 14

    def __post_init__(self) -> None:
        self._true_ranges: list[float] = []
        self._atr: float = 0.0
        self._initialised: bool = False

    def update(self, bar: OHLCV) -> None:
        """Feed one completed bar to the calculator."""
        tr = self._true_range(bar)

        if not self._initialised:
            # Accumulate until we have `period` true ranges
            self._true_ranges.append(tr)
            if len(self._true_ranges) == self.period:
                # Initialise with simple average of first N true ranges
                self._atr = sum(self._true_ranges) / self.period
                self._initialised = True
        else:
            # Wilder's smoothing: alpha = 1 / period
            alpha = 1.0 / self.period
            self._atr = alpha * tr + (1.0 - alpha) * self._atr

    @property
    def value(self) -> float:
        """Return current ATR (0.0 if still warming up)."""
        return self._atr if self._initialised else 0.0

    def _true_range(self, bar: OHLCV, prev_close: float = 0.0) -> float:
        """
        Calculate true range for this bar.
        WHY prev_close parameter: In a real feed, previous close is available.
        For testing or initial bars, default to 0.0.
        """
        high_low = bar.high - bar.low
        high_close = abs(bar.high - prev_close)
        low_close = abs(bar.low - prev_close)
        return max(high_low, high_close, low_close)

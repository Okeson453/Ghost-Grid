"""
regime/indicators/ema_ribbon.py
4-period EMA ribbon — alignment and slope strength.

EMA periods: 8, 13, 21, 34 (Fibonacci-based, standard SMC framework).

Alignment:
  full_alignment(LONG):    EMA8 > EMA13 > EMA21 > EMA34
  full_alignment(SHORT):   EMA8 < EMA13 < EMA21 < EMA34
  partial_alignment:       majority aligned but not all four

Slope strength: normalised 0.0–1.0
  = |EMA8 - EMA34| / ATR(14) on same timeframe
  0.0 = flat ribbon (no trend)
  1.0+ = strong trending (capped at 1.0)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from data.schema import OHLCV


@dataclass(frozen=True)
class EMAState:
    ema8: float
    ema13: float
    ema21: float
    ema34: float
    slope_strength: float  # 0.0–1.0 normalised
    separation: float  # |ema8 - ema34| in price units

    def full_alignment(self, direction: str) -> bool:
        if direction == "LONG":
            return self.ema8 > self.ema13 > self.ema21 > self.ema34
        return self.ema8 < self.ema13 < self.ema21 < self.ema34

    def partial_alignment(self, direction: str) -> bool:
        """At least 3 of 4 EMAs aligned."""
        emas = [self.ema8, self.ema13, self.ema21, self.ema34]
        if direction == "LONG":
            # Count adjacent pairs in correct order
            aligned = sum(1 for i in range(len(emas) - 1) if emas[i] > emas[i + 1])
        else:
            aligned = sum(1 for i in range(len(emas) - 1) if emas[i] < emas[i + 1])
        return aligned >= 2

    def is_fanned(self) -> bool:
        """
        WHY: a fanned ribbon (all EMAs separated by > 0 and trending)
        is the best regime for momentum entries. Flat ribbon = chop.
        """
        return self.slope_strength > 0.30


class EMARibbonCalculator:
    """
    Stateful EMA calculator for 4 periods.
    Call update() per bar. Read current state via .state.
    """

    PERIODS = (8, 13, 21, 34)

    def __init__(self) -> None:
        self._emas: dict[int, Optional[float]] = {p: None for p in self.PERIODS}
        self._alphas: dict[int, float] = {p: 2.0 / (p + 1) for p in self.PERIODS}
        self._bar_count = 0
        self._state: Optional[EMAState] = None

    @property
    def state(self) -> Optional[EMAState]:
        return self._state

    def update(self, bar: OHLCV, atr: float) -> Optional[EMAState]:
        """
        Feed one completed OHLCV bar.
        Returns updated EMAState, or None if insufficient bars.
        """
        price = bar.close
        self._bar_count += 1

        for p in self.PERIODS:
            alpha = self._alphas[p]
            if self._emas[p] is None:
                self._emas[p] = price
            else:
                self._emas[p] = self._emas[p] * (1 - alpha) + price * alpha

        # Need at least EMA34's period worth of bars for reliable values
        if self._bar_count < 34:
            return None

        ema8 = self._emas[8]
        ema13 = self._emas[13]
        ema21 = self._emas[21]
        ema34 = self._emas[34]

        separation = abs(ema8 - ema34)
        slope = min(separation / atr, 1.0) if atr > 0 else 0.0

        self._state = EMAState(
            ema8=ema8,
            ema13=ema13,
            ema21=ema21,
            ema34=ema34,
            slope_strength=slope,
            separation=separation,
        )
        return self._state

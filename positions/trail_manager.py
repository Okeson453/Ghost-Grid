"""
positions/trail_manager.py
Trailing stop arithmetic.

Rules:
  1. Trail only moves in the favorable direction (LONG: up, SHORT: down)
  2. Trail never moves against position (no tightening back)
  3. Trail distance = max(TRAIL_FLOOR_USD, ATR_1m × 0.5 × pip_value)
  4. Trail is in price units (not USD) — compared directly to current price

WHY ATR-adaptive trail:
Fixed USD trail would be too tight in high-volatility sessions and
too loose in low-volatility sessions. ATR adapts to market conditions.
"""

from __future__ import annotations
from typing import Optional
from config.constants import TRAIL_FLOOR_USD
from core.mode_selector import get_trail_floor_for_mode
from config.instruments import get_instrument


def compute_trail_distance(
    symbol: str,
    atr_1m: float,
    equity: float = 10_000.0,
    mode: str | None = None,
) -> float:
    """
    Compute trail distance in price units.

    Args:
        symbol:  Instrument symbol
        atr_1m:  Current M1 ATR in price units
        equity:  Account equity (used for USD floor conversion)

    Returns:
        Trail distance in price units
    """
    instr = get_instrument(symbol)

    # ATR-based distance: 0.5 × ATR_1m (in price units)
    atr_distance = atr_1m * 0.5

    # USD floor: mode-aware trail floor
    trail_floor_usd = TRAIL_FLOOR_USD if mode is None else get_trail_floor_for_mode(mode)
    floor_pips = trail_floor_usd / instr.pip_value
    floor_price_dist = floor_pips * instr.pip_size

    return max(atr_distance, floor_price_dist)


class TrailManager:
    """
    Manages trailing stop for one position.
    State: current trail_stop price.
    """

    def __init__(
        self,
        position_id: int,
        direction: str,
        symbol: str,
    ) -> None:
        self._id = position_id
        self._direction = direction
        self._symbol = symbol
        self._trail_stop: Optional[float] = None

    @property
    def trail_stop(self) -> Optional[float]:
        return self._trail_stop

    @property
    def is_armed(self) -> bool:
        return self._trail_stop is not None

    def arm(self, current_price: float, atr_1m: float, mode: str | None = None) -> float:
        """
        Arm the trailing stop at current_price - trail_distance (LONG)
        or current_price + trail_distance (SHORT).
        Returns the initial trail stop price.
        """
        dist = compute_trail_distance(self._symbol, atr_1m, mode=mode)

        if self._direction == "LONG":
            self._trail_stop = current_price - dist
        else:
            self._trail_stop = current_price + dist

        return self._trail_stop

    def update(self, current_price: float, atr_1m: float, mode: str | None = None) -> Optional[float]:
        """
        Move trail in favorable direction only.
        Returns new trail_stop if it moved, None if unchanged.
        """
        if self._trail_stop is None:
            return None

        dist = compute_trail_distance(self._symbol, atr_1m, mode=mode)
        new_stop: Optional[float] = None

        if self._direction == "LONG":
            proposed = current_price - dist
            if proposed > self._trail_stop:
                self._trail_stop = proposed
                new_stop = self._trail_stop

        else:  # SHORT
            proposed = current_price + dist
            if proposed < self._trail_stop:
                self._trail_stop = proposed
                new_stop = self._trail_stop

        return new_stop

    def is_hit(self, current_price: float) -> bool:
        """True if current price has crossed the trail stop."""
        if self._trail_stop is None:
            return False
        if self._direction == "LONG":
            return current_price <= self._trail_stop
        return current_price >= self._trail_stop

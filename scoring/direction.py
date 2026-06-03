"""
scoring/direction.py
Direction determination — which direction to score for a given snapshot.

WHY separate file: direction logic evolves. In Part 2 it was VWAP-based.
In Part 3 it uses regime + EMA ribbon. Keeping it separate prevents
BOS/CHoCH detectors from depending on regime state (circular import risk).

Algorithm:
  1. If EMA ribbon is fully aligned → ribbon direction
  2. If VWAP is clear → VWAP bias direction
  3. If session is OVERLAP → prefer LONG (slight statistical bias)
  4. Default: LONG
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from regime.indicators.ema_ribbon import EMARibbonCalculator

_ribbon_cache: dict[str, EMARibbonCalculator] = {}


def determine_direction(snap: MarketSnapshot) -> str:
    """
    Return the primary scoring direction for a MarketSnapshot.
    Returns "LONG" or "SHORT".
    """
    # ── Ribbon direction (highest priority) ───────────────────────────────
    if snap.m1:
        ribbon_calc = _get_ribbon(snap.symbol)
        ribbon = ribbon_calc.update(snap.m1[-1], snap.atr_1m)
        if ribbon is not None:
            if ribbon.full_alignment("LONG"):
                return "LONG"
            if ribbon.full_alignment("SHORT"):
                return "SHORT"

    # ── VWAP bias (fallback) ───────────────────────────────────────────────
    if snap.vwap > 0:
        return "LONG" if snap.tick.mid > snap.vwap else "SHORT"

    return "LONG"  # Default


def _get_ribbon(symbol: str) -> EMARibbonCalculator:
    if symbol not in _ribbon_cache:
        _ribbon_cache[symbol] = EMARibbonCalculator()
    return _ribbon_cache[symbol]

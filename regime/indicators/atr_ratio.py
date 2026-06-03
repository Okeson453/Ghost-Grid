"""
regime/indicators/atr_ratio.py
ATR expansion/contraction ratio.

ratio = ATR_1m / ATR_5m

> 1.1  → Expanding volatility (breakout / trend acceleration)
0.9–1.1 → Neutral
< 0.9  → Contracting volatility (chop / consolidation)

WHY this ratio: ATR_1m reacts faster to regime changes than ATR_5m.
When short-term volatility exceeds long-term, the market is accelerating.
When it's below, the market is digesting or ranging.
"""

from __future__ import annotations


def compute_atr_ratio(atr_1m: float, atr_5m: float) -> float:
    """
    Compute volatility expansion ratio.
    Returns 1.0 if either ATR is zero (neutral default).
    """
    if atr_5m == 0 or atr_1m == 0:
        return 1.0
    return atr_1m / atr_5m


def classify_volatility(ratio: float) -> str:
    """Classify ratio into EXPANDING | NEUTRAL | CONTRACTING."""
    if ratio > 1.1:
        return "EXPANDING"
    if ratio < 0.9:
        return "CONTRACTING"
    return "NEUTRAL"

"""
scoring/hlcp/trend_alignment.py
EMA ribbon trend alignment scorer — max 25 points.

Full alignment + strong slope:   25 pts
Full alignment, weak slope:      18 pts
Partial alignment:               12 pts
No alignment:                     0 pts

Session bonus: +5 pts if session is LONDON or OVERLAP
(applied in engine.py, not here — this function is pure score)
"""

from __future__ import annotations
from regime.indicators.ema_ribbon import EMAState


def score_trend_alignment(ribbon: EMAState, direction: str) -> int:
    """
    Score EMA ribbon alignment for given direction.

    Args:
        ribbon:    Current EMAState from EMARibbonCalculator
        direction: "LONG" | "SHORT"

    Returns: 0–25 (session bonus added externally)
    """
    if ribbon.full_alignment(direction):
        if ribbon.slope_strength > 0.75:
            return 25
        elif ribbon.slope_strength > 0.40:
            return 18
        else:
            return 10   # Aligned but barely sloping — weak signal
    elif ribbon.partial_alignment(direction):
        return 12
    else:
        return 0

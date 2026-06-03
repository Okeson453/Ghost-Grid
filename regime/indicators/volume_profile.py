"""
regime/indicators/volume_profile.py
Volume activity ratio.

ratio = current_bar.volume / avg(last N bars volume)

> 2.0  → High activity (breakout candidate)
1.2–2.0 → Above average
0.8–1.2 → Normal
< 0.8  → Low activity (avoid new entries)
"""

from __future__ import annotations
from data.schema import OHLCV


def compute_volume_ratio(bars: list[OHLCV], lookback: int = 5) -> float:
    """
    Ratio of current bar volume to recent average.
    Returns 1.0 if insufficient history.
    """
    if len(bars) < lookback + 1:
        return 1.0

    current   = bars[-1].volume
    avg       = sum(b.volume for b in bars[-(lookback + 1):-1]) / lookback

    return current / avg if avg > 0 else 1.0

"""
scoring/mpp/footprint.py
Volume cluster anomaly detection — identifies bars with statistically unusual volume concentration.

Identifies bars where volume concentration is statistically anomalous
compared to recent history, suggesting institutional participation.

Z-score of current volume vs rolling mean/std of recent N bars.
|Z| > 2.0 = statistically unusual → institutional footprint signal.

Returns: (bool, float) — (anomaly_detected, z_score)
"""

from __future__ import annotations
import math
from data.schema import OHLCV


def detect_volume_anomaly(
    m1_bars: list[OHLCV],
    lookback: int = 20,
) -> tuple[bool, float]:
    """
    Detect statistically unusual volume on the most recent bar.

    Returns:
        (anomaly_detected: bool, z_score: float)
    """
    if len(m1_bars) < lookback + 1:
        return False, 0.0

    history = [b.volume for b in m1_bars[-(lookback + 1):-1]]
    current = m1_bars[-1].volume

    mean_v = sum(history) / len(history)
    var_v  = sum((v - mean_v) ** 2 for v in history) / len(history)
    std_v  = math.sqrt(var_v) if var_v > 0 else 1e-9

    z = (current - mean_v) / std_v

    return abs(z) > 2.0, z

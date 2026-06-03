"""
positions/cvd_exit.py
Layer 4 exit — CVD divergence override.

CVD divergence: market makes a new high (LONG) but CVD_Z does NOT.
OR market makes a new low (SHORT) but CVD_Z does NOT.

WHY this fires first (Layer 4 checked before Layers 1–3):
CVD divergence is institutional accumulation/distribution breakdown.
It's the highest-conviction exit signal. Fire it immediately.

WHY Layer 4 (not earlier): Must allow at least 1 cycle of divergence
data to accumulate before firing (prevents false triggers on single bar).
"""

from __future__ import annotations
from data.schema import MarketSnapshot


def check_cvd_exit(snap: MarketSnapshot, direction: str) -> bool:
    """
    Detect CVD divergence and return True if position should close.

    Args:
        snap: Current MarketSnapshot with full CVD history
        direction: "LONG" | "SHORT"

    Returns:
        True if divergence detected, False otherwise
    """
    if not snap.cvd or len(snap.cvd) < 10:
        return False  # Need minimum history

    # Get recent price swing
    recent_ohlcv = snap.m5[-10:] if snap.m5 else []
    if not recent_ohlcv:
        return False

    closes = [bar.close for bar in recent_ohlcv]
    cvd_vals = list(snap.cvd.values())[-10:] if snap.cvd else []

    if len(closes) < 3 or len(cvd_vals) < 3:
        return False

    price_high = max(closes[-3:])
    price_low = min(closes[-3:])
    cvd_high = max(cvd_vals[-3:])
    cvd_low = min(cvd_vals[-3:])

    if direction == "LONG":
        # Price new high but CVD not → bearish divergence
        price_is_new_high = closes[-1] > price_high or price_high > max(closes[:-3])
        cvd_is_new_high = cvd_vals[-1] > cvd_high or cvd_high > max(cvd_vals[:-3])
        return price_is_new_high and not cvd_is_new_high
    else:
        # Price new low but CVD not → bullish divergence
        price_is_new_low = closes[-1] < price_low or price_low < min(closes[:-3])
        cvd_is_new_low = cvd_vals[-1] < cvd_low or cvd_low < min(cvd_vals[:-3])
        return price_is_new_low and not cvd_is_new_low

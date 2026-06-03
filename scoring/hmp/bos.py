"""
scoring/hmp/bos.py
Break of Structure (BOS) detector.

BOS (LONG): price closes ABOVE the most recent swing high on M5.
BOS (SHORT): price closes BELOW the most recent swing low on M5.

Momentum quality: |close - swing_level| / ATR_14(M5)
  > 0.70: High momentum BOS → full score
  ≤ 0.70: Low momentum BOS  → partial score

MTF alignment: M3 must also show a BOS in the same direction.
  If only M5 shows BOS: -8 point penalty (signal from higher TF only).

Input:  m5_bars: list[OHLCV], m3_bars: list[OHLCV], direction: str, atr_5m: float
Output: BOSResult
"""

from __future__ import annotations
from data.schema import OHLCV
from scoring.models import BOSResult
from scoring.hmp.swing import get_last_swing_high, get_last_swing_low


def detect_bos(
    m5_bars: list[OHLCV],
    m3_bars: list[OHLCV],
    direction: str,
    atr_5m: float,
) -> BOSResult:
    """
    Detect Break of Structure on M5 with M3 confirmation.

    WHY M5 primary, M3 confirmation:
    M5 gives structural significance; M3 confirmation eliminates
    false BOS from a single anomalous candle.
    """
    if len(m5_bars) < 10 or atr_5m == 0:
        return BOSResult(
            confirmed=False, momentum=0.0, swing_level=0.0, mtf_aligned=False
        )

    current_close = m5_bars[-1].close

    if direction == "LONG":
        swing = get_last_swing_high(m5_bars[:-1])  # Exclude current bar
        if swing is None:
            return BOSResult(
                confirmed=False, momentum=0.0, swing_level=0.0, mtf_aligned=False
            )
        confirmed = current_close > swing.price
        momentum = (
            abs(current_close - swing.price) / atr_5m if confirmed else 0.0
        )
        mtf = _check_m3_bos(m3_bars, "LONG", atr_5m) if confirmed else False

    else:  # SHORT
        swing = get_last_swing_low(m5_bars[:-1])
        if swing is None:
            return BOSResult(
                confirmed=False, momentum=0.0, swing_level=0.0, mtf_aligned=False
            )
        confirmed = current_close < swing.price
        momentum = (
            abs(current_close - swing.price) / atr_5m if confirmed else 0.0
        )
        mtf = _check_m3_bos(m3_bars, "SHORT", atr_5m) if confirmed else False

    return BOSResult(
        confirmed=confirmed,
        momentum=momentum,
        swing_level=swing.price,
        mtf_aligned=mtf,
    )


def _check_m3_bos(m3_bars: list[OHLCV], direction: str, atr: float) -> bool:
    """
    Lightweight M3 BOS check — no recursion into M1.
    Returns True if M3 also shows a recent BOS in the same direction.
    Uses last 15 M3 bars only.
    """
    if len(m3_bars) < 8:
        return False

    search = m3_bars[-15:]
    current_close = search[-1].close

    if direction == "LONG":
        swing = get_last_swing_high(search[:-1])
        return swing is not None and current_close > swing.price
    else:
        swing = get_last_swing_low(search[:-1])
        return swing is not None and current_close < swing.price

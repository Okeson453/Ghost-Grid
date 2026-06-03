"""
scoring/hmp/choch.py
Change of Character (CHoCH) detector.

CHoCH (LONG setup): After a downtrend, price breaks ABOVE a recent swing high
  on M3/M5 that was previously acting as resistance → market structure flip.

CHoCH (SHORT setup): After an uptrend, price breaks BELOW a recent swing low
  on M3/M5 that was previously acting as support.

Quality assessment:
  "high": Close fully beyond swing + M5 confirmation + volume > avg
  "med":  Close fully beyond swing (no volume confirmation)
  "low":  Wick beyond swing but close did not follow through

Input:  m3_bars, m5_bars, direction: str, atr_5m: float
Output: CHoCHResult
"""

from __future__ import annotations
from data.schema import OHLCV
from scoring.models import CHoCHResult
from scoring.hmp.swing import detect_swing_highs, detect_swing_lows


def detect_choch(
    m3_bars: list[OHLCV],
    m5_bars: list[OHLCV],
    direction: str,
) -> CHoCHResult:
    """Detect Change of Character for the given direction."""

    if len(m3_bars) < 10:
        return CHoCHResult(confirmed=False, quality="none", level=0.0)

    current = m3_bars[-1]

    if direction == "LONG":
        # Look for a break above the most recent M3 swing high
        swing_highs = detect_swing_highs(
            m3_bars[:-1], window=2, lookback=20
        )
        if not swing_highs:
            return CHoCHResult(confirmed=False, quality="none", level=0.0)
        target = swing_highs[0]

        close_beyond = current.close > target.price
        wick_beyond = current.high > target.price

        if not wick_beyond:
            return CHoCHResult(confirmed=False, quality="none", level=0.0)

        # M5 confirmation: check if M5 also shows close above the level
        m5_confirmed = _m5_confirms(m5_bars, target.price, "LONG")

        # Volume check: current bar volume > 20-bar average
        avg_vol = (
            sum(b.volume for b in m3_bars[-21:-1]) / 20
            if len(m3_bars) >= 21
            else 0
        )
        high_vol = current.volume > avg_vol * 1.2 if avg_vol > 0 else False

        if close_beyond and m5_confirmed and high_vol:
            quality = "high"
        elif close_beyond:
            quality = "med"
        else:
            quality = "low"

        return CHoCHResult(
            confirmed=close_beyond or wick_beyond,
            quality=quality, level=target.price
        )

    else:  # SHORT
        swing_lows = detect_swing_lows(
            m3_bars[:-1], window=2, lookback=20
        )
        if not swing_lows:
            return CHoCHResult(confirmed=False, quality="none", level=0.0)
        target = swing_lows[0]

        close_beyond = current.close < target.price
        wick_beyond = current.low < target.price

        if not wick_beyond:
            return CHoCHResult(confirmed=False, quality="none", level=0.0)

        m5_confirmed = _m5_confirms(m5_bars, target.price, "SHORT")
        avg_vol = (
            sum(b.volume for b in m3_bars[-21:-1]) / 20
            if len(m3_bars) >= 21
            else 0
        )
        high_vol = current.volume > avg_vol * 1.2 if avg_vol > 0 else False

        if close_beyond and m5_confirmed and high_vol:
            quality = "high"
        elif close_beyond:
            quality = "med"
        else:
            quality = "low"

        return CHoCHResult(
            confirmed=close_beyond or wick_beyond,
            quality=quality, level=target.price
        )


def _m5_confirms(m5_bars: list[OHLCV], level: float, direction: str) -> bool:
    """Check if M5 current bar close also confirms the CHoCH level break."""
    if len(m5_bars) < 2:
        return False
    current_m5 = m5_bars[-1]
    if direction == "LONG":
        return current_m5.close > level
    return current_m5.close < level

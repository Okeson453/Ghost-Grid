"""
scoring/hmp/fvg.py
Fair Value Gap (FVG) detector.

Bullish FVG: 3-candle pattern where candle[i+2].low > candle[i].high
  → Gap zone: [candle[i].high, candle[i+2].low]
  → Unfilled if current price > candle[i].high (hasn't re-entered)

Bearish FVG: 3-candle pattern where candle[i+2].high < candle[i].low
  → Gap zone: [candle[i+2].high, candle[i].low]
  → Unfilled if current price < candle[i].low (hasn't re-entered)

Search window: last 20 M3 bars.
Returns nearest unfilled FVG to current price.
Distance scored in ATR_5m units (< 0.5 = very close = high score).
"""

from __future__ import annotations
from typing import Optional
from data.schema import OHLCV
from scoring.models import FVGResult


_NO_FVG = FVGResult(
    found=False, top=0.0, bottom=0.0, gap_size=0.0,
    unfilled=False, distance_pct=999.0, direction="NONE",
)


def find_nearest_fvg(
    m3_bars: list[OHLCV],
    current_price: float,
    atr_5m: float,
    direction: str,
) -> FVGResult:
    """
    Find the nearest unfilled FVG in the last 20 M3 bars.

    Args:
        m3_bars:       M3 OHLCV list (oldest-first)
        current_price: Current bid (LONG) or ask (SHORT) price
        atr_5m:        ATR on M5 for distance normalisation
        direction:     "LONG" (look for bullish FVG) | "SHORT" (bearish FVG)

    Returns:
        FVGResult — found=False if no unfilled FVG exists
    """
    if len(m3_bars) < 3 or atr_5m == 0:
        return _NO_FVG

    search = m3_bars[-20:] if len(m3_bars) > 20 else m3_bars
    candidates: list[FVGResult] = []

    for i in range(len(search) - 2):
        c0, c2 = search[i], search[i + 2]
        fvg = _check_fvg(c0, c2, current_price, atr_5m, direction)
        if fvg.found and fvg.unfilled:
            candidates.append(fvg)

    if not candidates:
        return _NO_FVG

    # Return nearest to current price
    return min(candidates, key=lambda f: f.distance_pct)


def _check_fvg(
    c0: OHLCV,
    c2: OHLCV,
    current_price: float,
    atr_5m: float,
    direction: str,
) -> FVGResult:
    """Check one 3-candle combination for FVG pattern."""

    if direction == "LONG":
        # Bullish FVG: gap between c0.high and c2.low
        if c2.low > c0.high:
            gap_top = c2.low
            gap_bottom = c0.high
            gap_size = gap_top - gap_bottom
            # Unfilled: price hasn't re-entered the gap from above
            unfilled = current_price > gap_bottom
            # Distance: how far current price is from the gap boundary
            distance = (
                abs(current_price - gap_bottom) / atr_5m if atr_5m > 0 else 999.0
            )
            return FVGResult(
                found=True, top=gap_top, bottom=gap_bottom,
                gap_size=gap_size, unfilled=unfilled,
                distance_pct=distance, direction="BULLISH",
            )

    elif direction == "SHORT":
        # Bearish FVG: gap between c2.high and c0.low
        if c2.high < c0.low:
            gap_top = c0.low
            gap_bottom = c2.high
            gap_size = gap_top - gap_bottom
            unfilled = current_price < gap_top
            distance = (
                abs(current_price - gap_top) / atr_5m if atr_5m > 0 else 999.0
            )
            return FVGResult(
                found=True, top=gap_top, bottom=gap_bottom,
                gap_size=gap_size, unfilled=unfilled,
                distance_pct=distance, direction="BEARISH",
            )

    return FVGResult(
        found=False, top=0.0, bottom=0.0, gap_size=0.0,
        unfilled=False, distance_pct=999.0, direction="NONE",
    )

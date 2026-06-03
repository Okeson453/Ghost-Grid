"""
scoring/hmp/order_block.py
Order Block (OB) detector.

An Order Block is the last up-candle before a significant bearish move (bearish OB)
or the last down-candle before a significant bullish move (bullish OB).

Bullish OB (LONG signal): Last bearish candle before a strong up-move.
  Identified when a series of bullish candles follows, and price returns to test
  the bearish candle's zone.

Bearish OB (SHORT signal): Last bullish candle before a strong down-move.

Freshness: OB is valid only if test_count < 3.
  After 3 tests, institutional interest is assumed exhausted.

Imbalance ratio: Volume of OB creation candle vs average.
  > 0.6 imbalance = strong institutional footprint.
"""

from __future__ import annotations
from typing import Optional
from data.schema import OHLCV
from scoring.models import OrderBlockResult


_NO_OB = OrderBlockResult(
    found=False, top=0.0, bottom=0.0,
    test_count=0, imbalance_ratio=0.0, stale=True,
)


def find_active_ob(
    m5_bars: list[OHLCV],
    current_price: float,
    direction: str,
) -> OrderBlockResult:
    """
    Find the most relevant active Order Block.
    Returns _NO_OB if none found.
    """
    if len(m5_bars) < 15:
        return _NO_OB

    avg_vol = sum(b.volume for b in m5_bars[-20:]) / min(20, len(m5_bars))
    search = m5_bars[-30:] if len(m5_bars) >= 30 else m5_bars

    if direction == "LONG":
        return _find_bullish_ob(search, current_price, avg_vol)
    return _find_bearish_ob(search, current_price, avg_vol)


def _find_bullish_ob(
    bars: list[OHLCV],
    current_price: float,
    avg_volume: float,
) -> OrderBlockResult:
    """
    Bullish OB: last bearish candle before a strong up-move of ≥3 consecutive bullish bars.
    Current price must be near (within 2× the OB range above) the OB zone.
    """
    for i in range(len(bars) - 4, 1, -1):
        candidate = bars[i]
        if not candidate.is_bearish:
            continue

        # Check if followed by ≥3 bullish bars
        subsequent = bars[i + 1 : i + 4]
        if len(subsequent) < 3:
            continue
        if not all(b.is_bullish for b in subsequent):
            continue

        ob_top = candidate.open  # Bearish candle: open > close
        ob_bottom = candidate.close
        ob_size = ob_top - ob_bottom

        # Current price must be within proximity of OB
        if current_price < ob_bottom or current_price > ob_top + ob_size * 2:
            continue

        # Count tests: how many times has price touched this zone since OB creation
        test_count = _count_ob_tests(bars[i + 4:], ob_top, ob_bottom, "LONG")

        imbalance = candidate.volume / avg_volume if avg_volume > 0 else 0.0

        return OrderBlockResult(
            found=True,
            top=ob_top,
            bottom=ob_bottom,
            test_count=test_count,
            imbalance_ratio=imbalance,
            stale=test_count >= 3,
        )

    return _NO_OB


def _find_bearish_ob(
    bars: list[OHLCV],
    current_price: float,
    avg_volume: float,
) -> OrderBlockResult:
    """Bearish OB: last bullish candle before a strong down-move of ≥3 consecutive bearish bars."""
    for i in range(len(bars) - 4, 1, -1):
        candidate = bars[i]
        if not candidate.is_bullish:
            continue

        subsequent = bars[i + 1 : i + 4]
        if len(subsequent) < 3:
            continue
        if not all(b.is_bearish for b in subsequent):
            continue

        ob_top = candidate.close  # Bullish candle: close > open
        ob_bottom = candidate.open
        ob_size = ob_top - ob_bottom

        if current_price > ob_top or current_price < ob_bottom - ob_size * 2:
            continue

        test_count = _count_ob_tests(
            bars[i + 4:], ob_top, ob_bottom, "SHORT"
        )
        imbalance = candidate.volume / avg_volume if avg_volume > 0 else 0.0

        return OrderBlockResult(
            found=True,
            top=ob_top,
            bottom=ob_bottom,
            test_count=test_count,
            imbalance_ratio=imbalance,
            stale=test_count >= 3,
        )

    return _NO_OB


def _count_ob_tests(
    bars_after: list[OHLCV],
    ob_top: float,
    ob_bottom: float,
    direction: str,
) -> int:
    """Count bars where price entered the OB zone after creation."""
    count = 0
    for bar in bars_after:
        if direction == "LONG":
            if bar.low <= ob_top and bar.high >= ob_bottom:
                count += 1
        else:
            if bar.high >= ob_bottom and bar.low <= ob_top:
                count += 1
    return count

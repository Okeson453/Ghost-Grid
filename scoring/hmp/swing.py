"""
scoring/hmp/swing.py
Fractal swing high/low detector.

A swing high is a bar whose high is higher than both adjacent N bars on each side.
A swing low  is a bar whose low  is lower  than both adjacent N bars on each side.

Default fractal window: 2 bars each side (ZigZag-style, N=2).

This module has NO dependencies on any other scoring module.
It is a pure mathematical function on list[OHLCV].
"""

from __future__ import annotations
from typing import Optional
from data.schema import OHLCV
from scoring.models import SwingPoint


def detect_swing_highs(
    bars: list[OHLCV],
    window: int = 2,
    lookback: int = 20,
) -> list[SwingPoint]:
    """
    Detect fractal swing highs in the last `lookback` bars.
    Returns list of SwingPoints, most recent first.

    Args:
        bars:     OHLCV list (oldest-first)
        window:   Number of bars each side that must be lower
        lookback: Only search the last N bars
    """
    if len(bars) < window * 2 + 1:
        return []

    search_slice = bars[-lookback:] if len(bars) > lookback else bars
    highs = []

    for i in range(window, len(search_slice) - window):
        candidate = search_slice[i]
        left = search_slice[i - window : i]
        right = search_slice[i + 1 : i + window + 1]

        is_swing_high = (
            all(b.high < candidate.high for b in left)
            and all(b.high < candidate.high for b in right)
        )

        if is_swing_high:
            # Convert local index to bars-list index (from end)
            bars_index = -(len(search_slice) - i)
            highs.append(
                SwingPoint(
                    price=candidate.high,
                    timestamp_ms=candidate.timestamp_ms,
                    swing_type="HIGH",
                    bar_index=bars_index,
                )
            )

    return list(reversed(highs))  # Most recent first


def detect_swing_lows(
    bars: list[OHLCV],
    window: int = 2,
    lookback: int = 20,
) -> list[SwingPoint]:
    """
    Detect fractal swing lows. Same logic as swing highs, inverted.
    Returns list of SwingPoints, most recent first.
    """
    if len(bars) < window * 2 + 1:
        return []

    search_slice = bars[-lookback:] if len(bars) > lookback else bars
    lows = []

    for i in range(window, len(search_slice) - window):
        candidate = search_slice[i]
        left = search_slice[i - window : i]
        right = search_slice[i + 1 : i + window + 1]

        is_swing_low = (
            all(b.low > candidate.low for b in left)
            and all(b.low > candidate.low for b in right)
        )

        if is_swing_low:
            bars_index = -(len(search_slice) - i)
            lows.append(
                SwingPoint(
                    price=candidate.low,
                    timestamp_ms=candidate.timestamp_ms,
                    swing_type="LOW",
                    bar_index=bars_index,
                )
            )

    return list(reversed(lows))  # Most recent first


def get_last_swing_high(bars: list[OHLCV], window: int = 2) -> Optional[SwingPoint]:
    """Return the most recent swing high, or None."""
    highs = detect_swing_highs(bars, window=window, lookback=30)
    return highs[0] if highs else None


def get_last_swing_low(bars: list[OHLCV], window: int = 2) -> Optional[SwingPoint]:
    """Return the most recent swing low, or None."""
    lows = detect_swing_lows(bars, window=window, lookback=30)
    return lows[0] if lows else None

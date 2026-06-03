"""
tests/fixtures/sample_ohlcv.py
OHLCV bar factory.

Creates realistic bar sequences for testing aggregation, scoring, and risk.
"""

from __future__ import annotations
import time
from typing import Optional

from data.schema import OHLCV


def make_bar(
    symbol: str = "EURUSD",
    timeframe: str = "M1",
    open: float = 1.0850,
    high: float = 1.0855,
    low: float = 1.0845,
    close: float = 1.0852,
    volume: int = 1000,
    timestamp_ms: Optional[int] = None,
) -> OHLCV:
    """
    Create a single OHLCV bar.

    All defaults produce valid EURUSD M1 bar.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    return OHLCV(
        symbol=symbol,
        timeframe=timeframe,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        timestamp_ms=timestamp_ms,
    )


def make_bullish_trend(
    count: int,
    base: float = 1.0850,
    step: float = 0.0005,
    symbol: str = "EURUSD",
    timeframe: str = "M1",
    start_ts_ms: Optional[int] = None,
    interval_ms: int = 60000,
) -> list[OHLCV]:
    """
    Create a bullish trending bar sequence (closes higher each bar).

    base: starting close price
    step: price increase per bar
    interval_ms: milliseconds between bar timestamps (default 1 min = 60000)
    """
    if start_ts_ms is None:
        start_ts_ms = int(time.time() * 1000)

    bars = []
    for i in range(count):
        ts = start_ts_ms + (i * interval_ms)
        close = base + (step * (i + 1))
        open = close - (step * 0.3)
        high = close + (step * 0.2)
        low = open - (step * 0.1)

        bar = make_bar(
            symbol=symbol,
            timeframe=timeframe,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=1000,
            timestamp_ms=ts,
        )
        bars.append(bar)

    return bars


def make_bearish_trend(
    count: int,
    base: float = 1.0850,
    step: float = 0.0005,
    symbol: str = "EURUSD",
    timeframe: str = "M1",
    start_ts_ms: Optional[int] = None,
    interval_ms: int = 60000,
) -> list[OHLCV]:
    """
    Create a bearish trending bar sequence (closes lower each bar).

    base: starting close price
    step: price decrease per bar
    interval_ms: milliseconds between bar timestamps (default 1 min = 60000)
    """
    if start_ts_ms is None:
        start_ts_ms = int(time.time() * 1000)

    bars = []
    for i in range(count):
        ts = start_ts_ms + (i * interval_ms)
        close = base - (step * (i + 1))
        open = close + (step * 0.3)
        high = open + (step * 0.1)
        low = close - (step * 0.2)

        bar = make_bar(
            symbol=symbol,
            timeframe=timeframe,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=1000,
            timestamp_ms=ts,
        )
        bars.append(bar)

    return bars


def make_ranging_bars(
    count: int,
    mid: float = 1.0850,
    range_: float = 0.0010,
    symbol: str = "EURUSD",
    timeframe: str = "M1",
    start_ts_ms: Optional[int] = None,
    interval_ms: int = 60000,
) -> list[OHLCV]:
    """
    Create a ranging (sideways) bar sequence.

    mid: midpoint of the range
    range_: total range size (high - low)
    interval_ms: milliseconds between bar timestamps
    """
    if start_ts_ms is None:
        start_ts_ms = int(time.time() * 1000)

    bars = []
    high = mid + (range_ / 2)
    low = mid - (range_ / 2)

    for i in range(count):
        ts = start_ts_ms + (i * interval_ms)
        # Alternate between tops and bottoms
        if i % 2 == 0:
            close = high - (range_ * 0.1)
            open = low + (range_ * 0.2)
        else:
            close = low + (range_ * 0.1)
            open = high - (range_ * 0.2)

        bar = make_bar(
            symbol=symbol,
            timeframe=timeframe,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=1000,
            timestamp_ms=ts,
        )
        bars.append(bar)

    return bars

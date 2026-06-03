"""
tests/fixtures/sample_ticks.py
Synthetic tick message factory.

Creates realistic tick data for testing the data pipeline.
All ticks default to EURUSD in LONDON session.
"""

from __future__ import annotations
import time
from typing import Optional

from bridge.protocol import TickMessage


def make_tick(
    symbol: str = "EURUSD",
    timestamp_ms: Optional[int] = None,
    bid: float = 1.0850,
    ask: float = 1.0851,
    tick_volume: int = 1,
    dominant_side: str = "BUY",
    cvd_running: float = 0.0,
) -> TickMessage:
    """
    Create a single TickMessage.

    Default timestamp: current time in milliseconds.
    All defaults produce valid EURUSD ticks.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    return TickMessage(
        symbol=symbol,
        timestamp_ms=timestamp_ms,
        bid=bid,
        ask=ask,
        tick_volume=tick_volume,
        dominant_side=dominant_side,
        cvd_running=cvd_running,
    )


def make_tick_sequence(
    count: int,
    symbol: str = "EURUSD",
    start_ts_ms: Optional[int] = None,
    start_bid: float = 1.0850,
    start_ask: float = 1.0851,
    direction: str = "up",
    interval_ms: int = 50,
) -> list[TickMessage]:
    """
    Create a time-ordered sequence of ticks.

    direction: "up" | "down" | "flat"
    - "up": bid/ask increment each tick
    - "down": bid/ask decrement each tick
    - "flat": bid/ask stay constant

    interval_ms: milliseconds between tick timestamps
    """
    if start_ts_ms is None:
        start_ts_ms = int(time.time() * 1000)

    ticks = []
    bid = start_bid
    ask = start_ask
    cvd = 0.0

    for i in range(count):
        # Update price based on direction
        if direction == "up":
            bid += 0.0001  # 1 pip
            ask += 0.0001
            cvd += 10.0  # Rising CVD
        elif direction == "down":
            bid -= 0.0001
            ask -= 0.0001
            cvd -= 10.0  # Falling CVD
        # else: flat (no change)

        ts = start_ts_ms + (i * interval_ms)
        dominant = "BUY" if direction == "up" else "SELL"

        tick = make_tick(
            symbol=symbol,
            timestamp_ms=ts,
            bid=bid,
            ask=ask,
            tick_volume=1,
            dominant_side=dominant,
            cvd_running=cvd,
        )
        ticks.append(tick)

    return ticks

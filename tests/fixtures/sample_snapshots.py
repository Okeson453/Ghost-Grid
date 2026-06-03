"""
tests/fixtures/sample_snapshots.py
Pre-built MarketSnapshot factory.

Creates complete market snapshots for testing scoring and risk modules.
"""

from __future__ import annotations
import time
from typing import Optional

from data.schema import Tick, OHLCV, MarketSnapshot
from .sample_ticks import make_tick
from .sample_ohlcv import make_bullish_trend, make_bar


def make_snapshot(
    symbol: str = "EURUSD",
    tick_bid: float = 1.0850,
    tick_ask: float = 1.0851,
    m1: Optional[OHLCV] = None,
    m3: Optional[OHLCV] = None,
    m5: Optional[OHLCV] = None,
    cvd_history: Optional[list[float]] = None,
    vwap: float = 1.0850,
    atr_1m: float = 0.0010,
    atr_5m: float = 0.0015,
    session: str = "LONDON",
    regime: str = "TREND",
) -> MarketSnapshot:
    """
    Create a complete MarketSnapshot.

    Sensible defaults: LONDON session, TREND regime, rising CVD.
    Uses make_bullish_trend as default for OHLCV bars.
    """
    # Default tick
    tick = make_tick(
        symbol=symbol,
        bid=tick_bid,
        ask=tick_ask,
        dominant_side="BUY",
        cvd_running=100.0,
    )

    # Default M1, M3, M5 bars if not provided
    if m1 is None:
        m1 = make_bar(symbol=symbol, timeframe="M1", close=tick_bid + 0.0005)
    if m3 is None:
        m3 = make_bar(symbol=symbol, timeframe="M3", close=tick_bid + 0.0010)
    if m5 is None:
        m5 = make_bar(symbol=symbol, timeframe="M5", close=tick_bid + 0.0015)

    # Default CVD history: rising trend
    if cvd_history is None:
        cvd_history = [float(i * 10) for i in range(20)]  # 0, 10, 20, ..., 190

    return MarketSnapshot(
        symbol=symbol,
        tick=tick,
        m1=m1,
        m3=m3,
        m5=m5,
        cvd_history=cvd_history,
        vwap=vwap,
        atr_1m=atr_1m,
        atr_5m=atr_5m,
        session=session,
        regime=regime,
    )

"""
data/schema.py
Core data models shared by all modules.

SOURCE: GHOST-GRID-MT5-Design.md § 1.2 Market Data Schema

This file defines the canonical representation of market data:
- Tick: single price quote (bid/ask)
- OHLCV: aggregated bar (1m, 3m, 5m)
- BarBuffer: rolling window of recent bars
- MarketSnapshot: complete market state for one symbol at one instant

All public dataclasses are frozen (immutable). This prevents
accidental mutation and makes reasoning about data flow easier.

WHY frozen MarketSnapshot: Once a snapshot is created, it represents
a point-in-time market state. Scoring engines never mutate snapshots —
they use dataclasses.replace() to create new versions with modified
regime/session fields. This enforces functional composition and makes
debugging easier (no hidden state changes).

Design spec fields preserved:
- Tick.cvd: cumulative volume delta (running), from EA via named pipe
- OHLCV.timeframe: "M1" | "M3" | "M5" (design spec requirement)
- MarketSnapshot.cvd_history: last 200 CVD values (1-per-minute)
- MarketSnapshot.regime: 4-state enum (TREND|CHOP|BREAKOUT|REVERSAL)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from config import get_instrument


@dataclass(frozen=True)
class Tick:
    """Single price quote from MT5."""

    symbol: str
    timestamp_ms: int  # Unix milliseconds, UTC
    bid: float
    ask: float
    tick_volume: int  # Volume at this tick
    dominant_side: str  # "BUY" | "SELL" | "NEUTRAL"
    cvd_running: float  # Cumulative volume delta (session-reset)
    session: str  # "ASIA" | "LONDON" | "NY" | "OVERLAP" | "INACTIVE"

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pips(self) -> float:
        """
        Approximate spread in pips. Assumes 4-digit precision;
        adjust in get_instrument if using Japanese yen or gold.
        """
        return (self.ask - self.bid) / 0.0001


@dataclass(frozen=True)
class OHLCV:
    """Aggregated bar (M1, M3, M5)."""

    symbol: str
    timeframe: str  # "M1" | "M3" | "M5"
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp_ms: int  # Close time in ms, UTC

    @property
    def body(self) -> float:
        """Absolute size of open-close range."""
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        """Distance from close to high (or open to high if bearish)."""
        top = max(self.open, self.close)
        return self.high - top

    @property
    def lower_wick(self) -> float:
        """Distance from close to low (or open to low if bearish)."""
        bottom = min(self.open, self.close)
        return bottom - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class BarBuffer:
    """Rolling window of recent bars for one symbol/timeframe."""

    symbol: str
    timeframe: str
    max_size: int
    _bars: list[OHLCV] = None

    def __post_init__(self) -> None:
        if self._bars is None:
            self._bars = []

    def append(self, bar: OHLCV) -> None:
        """Add a bar and trim to max_size (oldest first)."""
        self._bars.append(bar)
        if len(self._bars) > self.max_size:
            self._bars = self._bars[-self.max_size :]

    @property
    def bars(self) -> list[OHLCV]:
        """Return a copy of all bars, oldest first."""
        return list(self._bars)

    @property
    def latest(self) -> Optional[OHLCV]:
        """Return the most recent bar, or None if buffer empty."""
        return self._bars[-1] if self._bars else None

    def __len__(self) -> int:
        return len(self._bars)


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Complete market state for one symbol at one moment.
    Frozen: never mutate, use dataclasses.replace() instead.

    WHY frozen: This enforces immutability across the entire
    scoring pipeline. Scoring engines receive a snapshot, compute
    regime/scores, and emit a NEW snapshot via replace().
    No hidden state mutations → easier to reason about and debug.
    """

    symbol: str
    tick: Tick
    m1: OHLCV
    m3: OHLCV
    m5: OHLCV
    cvd_history: list[float]  # Last 200 CVD values (1-per-minute), oldest first
    vwap: float  # Current session VWAP
    atr_1m: float  # Wilder's ATR on M1 bars
    atr_5m: float  # Wilder's ATR on M5 bars
    session: str  # Session at tick.timestamp_ms
    regime: str  # Regime fingerprint: "TREND" | "CHOP" | "BREAKOUT" | "REVERSAL"

    @property
    def spread_pips(self) -> float:
        """Convert bid/ask spread to pips using instrument pip_size."""
        instr = get_instrument(self.symbol)
        return (self.tick.ask - self.tick.bid) / instr.pip_size

    @property
    def latest_m1(self) -> OHLCV:
        """Most recent M1 bar (for convenience)."""
        return self.m1

    @property
    def latest_m5(self) -> OHLCV:
        """Most recent M5 bar (for convenience)."""
        return self.m5

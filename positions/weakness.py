"""
positions/weakness.py
Layer 3 weakness detector — 3 concurrent signals required.

Signals:
  1. RSI(3) extreme: > 75 (LONG exhaustion) or < 25 (SHORT exhaustion)
  2. Engulfing candle against position direction (bearish engulf for LONG)
  3. Volume cliff: current bar volume < 30% of 5-bar average

WHY require all three:
Any single signal alone is noisy. Volume cliff with no price action
is just a quiet moment. RSI extreme without volume dropout may
precede a breakout. All three together = genuine exhaustion.
"""

from __future__ import annotations
from dataclasses import dataclass
from data.schema import OHLCV


@dataclass(frozen=True)
class WeaknessSignal:
    rsi_extreme: bool
    engulfing: bool
    vol_cliff: bool
    all_three: bool
    rsi_value: float


def detect_weakness(
    m1_bars: list,
    direction: str,
) -> WeaknessSignal:
    """
    Check for Layer 3 weakness across 3 concurrent signals.

    Args:
        m1_bars:   M1 OHLCV list (oldest-first), requires ≥ 6 bars
        direction: "LONG" | "SHORT" — position direction being protected
    """
    if len(m1_bars) < 6:
        return WeaknessSignal(False, False, False, False, 50.0)

    current = m1_bars[-1]
    prev = m1_bars[-2]

    # ── RSI(3) extreme ────────────────────────────────────────────────────
    rsi = _rsi3(m1_bars)
    if direction == "LONG":
        rsi_extreme = rsi > 75
    else:
        rsi_extreme = rsi < 25

    # ── Engulfing candle ──────────────────────────────────────────────────
    engulfing = _is_engulfing(current, prev, direction)

    # ── Volume cliff ──────────────────────────────────────────────────────
    avg_vol = sum(b.volume for b in m1_bars[-6:-1]) / 5
    vol_cliff = current.volume < avg_vol * 0.30 if avg_vol > 0 else False

    all_three = rsi_extreme and engulfing and vol_cliff

    return WeaknessSignal(
        rsi_extreme=rsi_extreme,
        engulfing=engulfing,
        vol_cliff=vol_cliff,
        all_three=all_three,
        rsi_value=rsi,
    )


def _rsi3(bars: list) -> float:
    """Calculate RSI(3)."""
    period = 3
    if len(bars) < period + 1:
        return 50.0
    closes = [b.close for b in bars[-(period + 1) :]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + ag / al))


def _is_engulfing(
    current,
    prev,
    direction: str,
) -> bool:
    """
    Engulfing candle against position direction:
    LONG: bearish engulfing (current bearish + body engulfs prev bullish)
    SHORT: bullish engulfing (current bullish + body engulfs prev bearish)
    """
    if direction == "LONG":
        return (
            current.close < current.open
            and prev.close > prev.open
            and current.open >= prev.close
            and current.close <= prev.open
        )
    else:
        return (
            current.close > current.open
            and prev.close < prev.open
            and current.open <= prev.close
            and current.close >= prev.open
        )

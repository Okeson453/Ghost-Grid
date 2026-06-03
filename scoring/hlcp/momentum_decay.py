"""
scoring/hlcp/momentum_decay.py
Momentum decay / exhaustion detector — max 15 points.

Two signals combined:
  1. RSI(7) reaching extreme + turning back (2nd derivative negative for LONG)
  2. Volume declining over last 3 bars (volume cliff)

Scoring:
  Both signals present:  15 pts
  RSI extreme only:       8 pts
  Volume decay only:      4 pts
  Neither:                0 pts

WHY RSI(7) not RSI(14):
Shorter period reacts faster. At scalping timeframes we want to catch
exhaustion within 1–2 M1 bars, not 14.
"""

from __future__ import annotations
from dataclasses import dataclass
from data.schema import OHLCV


@dataclass(frozen=True)
class MomentumDecaySignal:
    rsi_extreme:    bool
    rsi_value:      float
    volume_decay:   bool
    all_two:        bool    # Both signals present


def detect_momentum_decay(
    m1_bars: list[OHLCV],
    direction: str,
) -> MomentumDecaySignal:
    """
    Detect momentum exhaustion for the given direction.

    WHY check for decay of the TRADE direction:
    We want to exit or avoid entry when the move we're riding
    is showing signs of running out of energy.
    """
    if len(m1_bars) < 10:
        return MomentumDecaySignal(False, 50.0, False, False)

    rsi   = _rsi7(m1_bars)
    vol_d = _volume_decaying(m1_bars, lookback=3)

    if direction == "LONG":
        rsi_extreme = rsi > 72
    else:
        rsi_extreme = rsi < 28

    all_two = rsi_extreme and vol_d

    return MomentumDecaySignal(
        rsi_extreme=rsi_extreme,
        rsi_value=rsi,
        volume_decay=vol_d,
        all_two=all_two,
    )


def score_momentum_decay(signal: MomentumDecaySignal) -> int:
    """Convert decay signal to 0–15 score (higher = more exhaustion)."""
    if signal.all_two:
        return 15
    if signal.rsi_extreme:
        return 8
    if signal.volume_decay:
        return 4
    return 0


def _rsi7(bars: list[OHLCV]) -> float:
    period = 7
    if len(bars) < period + 1:
        return 50.0
    closes = [b.close for b in bars[-(period + 1):]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + ag / al))


def _volume_decaying(bars: list[OHLCV], lookback: int = 3) -> bool:
    """True if volume has declined consecutively over last `lookback` bars."""
    if len(bars) < lookback + 1:
        return False
    recent = [b.volume for b in bars[-lookback:]]
    return all(recent[i] < recent[i-1] for i in range(1, len(recent)))

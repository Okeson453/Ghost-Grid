"""
scoring/mpp/absorption.py
Institutional absorption detector — max 15 points.

Patterns detected:
  1. Sweep-and-reclaim: price wicks below/above a key level then closes back
     inside → trapped retail traders, institutional reversal
  2. High-volume rejection: large wick with small body + volume > 2× average
     → institutional rejection of price level

Scoring:
  Sweep-and-reclaim confirmed: 15 pts
  High-volume rejection:       10 pts
  Unusual volume cluster only:  6 pts
  None:                         0 pts
"""

from __future__ import annotations
from dataclasses import dataclass
from data.schema import OHLCV


@dataclass(frozen=True)
class AbsorptionSignal:
    sweep_and_reclaim: bool
    high_vol_rejection: bool
    unusual_volume:     bool


def detect_absorption(
    m1_bars:  list[OHLCV],
    direction: str,
) -> AbsorptionSignal:
    """
    Detect absorption patterns on M1 bars.

    Args:
        m1_bars:   M1 OHLCV bars (oldest-first), requires ≥ 10 bars
        direction: "LONG" | "SHORT"
    """
    if len(m1_bars) < 10:
        return AbsorptionSignal(False, False, False)

    current  = m1_bars[-1]
    prev     = m1_bars[-2]
    avg_vol  = sum(b.volume for b in m1_bars[-11:-1]) / 10

    # ── Sweep-and-reclaim ─────────────────────────────────────────────────
    sar = _detect_sweep_reclaim(current, prev, direction)

    # ── High-volume rejection ─────────────────────────────────────────────
    hvr = _detect_hv_rejection(current, avg_vol, direction)

    # ── Unusual volume cluster ────────────────────────────────────────────
    unusual_vol = current.volume > avg_vol * 1.8

    return AbsorptionSignal(
        sweep_and_reclaim=sar,
        high_vol_rejection=hvr,
        unusual_volume=unusual_vol,
    )


def score_absorption(signal: AbsorptionSignal) -> int:
    """Convert absorption signal to 0–15 score."""
    if signal.sweep_and_reclaim:
        return 15
    if signal.high_vol_rejection:
        return 10
    if signal.unusual_volume:
        return 6
    return 0


def _detect_sweep_reclaim(
    current: OHLCV,
    prev:    OHLCV,
    direction: str,
) -> bool:
    """
    Sweep-and-reclaim: price spikes beyond prev bar's extreme then closes back.
    LONG: current.low < prev.low but current.close > prev.low (reclaim)
    SHORT: current.high > prev.high but current.close < prev.high (reclaim)
    """
    if direction == "LONG":
        swept  = current.low < prev.low
        reclaim = current.close > prev.low
        return swept and reclaim
    else:
        swept  = current.high > prev.high
        reclaim = current.close < prev.high
        return swept and reclaim


def _detect_hv_rejection(
    bar:       OHLCV,
    avg_vol:   float,
    direction: str,
) -> bool:
    """
    High-volume rejection: wick > 2× body + volume > 2× average.
    LONG: lower wick is the rejection (buyers absorbing sellers)
    SHORT: upper wick is the rejection (sellers absorbing buyers)
    """
    if avg_vol == 0:
        return False

    high_vol = bar.volume > avg_vol * 2.0
    body     = bar.body

    if direction == "LONG":
        wick_dominated = bar.lower_wick > body * 2.0
    else:
        wick_dominated = bar.upper_wick > body * 2.0

    return high_vol and wick_dominated

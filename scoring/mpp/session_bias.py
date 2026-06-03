"""
scoring/mpp/session_bias.py
Session directional bias scorer — max 20 points.

Bias signals:
  1. VWAP alignment: price above/below session VWAP
  2. M1 bar consistency: last 6 bars predominantly bullish/bearish
  3. Combined: both aligned → "strong directional" → 20 pts
               Either alone   → "directional"        → 9 pts

WHY VWAP: VWAP is the institutional average price. Price consistently
above VWAP signals net institutional buying; below = net selling.
Combined with bar consistency it identifies session drift direction.
"""

from __future__ import annotations
from dataclasses import dataclass
from data.schema import OHLCV


@dataclass(frozen=True)
class SessionBiasSignal:
    strong_directional: bool
    directional:        bool
    vwap_above:         bool    # True if price > vwap
    bar_consistency:    float   # 0.0–1.0, ratio of bars in direction


def compute_session_bias(
    m1_bars:   list[OHLCV],
    vwap:      float,
    current_price: float,
    direction: str,
    lookback:  int = 6,
) -> SessionBiasSignal:
    """
    Compute session directional bias.

    Args:
        m1_bars:       M1 OHLCV list (oldest-first)
        vwap:          Current session VWAP
        current_price: Current mid price
        direction:     "LONG" | "SHORT" — trade direction being scored
        lookback:      Number of recent M1 bars to assess consistency

    Returns:
        SessionBiasSignal
    """
    if len(m1_bars) < lookback or vwap == 0:
        return SessionBiasSignal(False, False, False, 0.0)

    # ── VWAP check ────────────────────────────────────────────────────────
    price_above_vwap = current_price > vwap

    if direction == "LONG":
        vwap_aligned = price_above_vwap
    else:
        vwap_aligned = not price_above_vwap

    # ── Bar consistency ───────────────────────────────────────────────────
    recent = m1_bars[-lookback:]
    if direction == "LONG":
        bullish_count = sum(1 for b in recent if b.is_bullish)
        consistency   = bullish_count / lookback
        bar_aligned   = consistency >= 0.67   # ≥4/6 bullish
    else:
        bearish_count = sum(1 for b in recent if b.is_bearish)
        consistency   = bearish_count / lookback
        bar_aligned   = consistency >= 0.67   # ≥4/6 bearish

    strong = vwap_aligned and bar_aligned
    either = vwap_aligned or bar_aligned

    return SessionBiasSignal(
        strong_directional=strong,
        directional=either,
        vwap_above=price_above_vwap,
        bar_consistency=consistency,
    )


def score_session_bias(signal: SessionBiasSignal) -> int:
    """Convert bias signal to 0–20 score."""
    if signal.strong_directional:
        return 20
    if signal.directional:
        return 9
    return 0

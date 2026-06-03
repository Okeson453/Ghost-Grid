"""
scoring/mpp/cvd_divergence.py
CVD divergence detector — Kalman-approximated via EMA smoothing.

Algorithm:
  1. Smooth CVD history with EMA (α=0.15) → "fair value" CVD line
  2. Residual per bar = raw_CVD - smoothed_CVD
  3. Z-score = residual[-1] / std(residuals[-20:])
  4. Price trend: M1 close[-1] vs close[-10]
  5. CVD trend:   cvd[-1] vs cvd[-10]
  6. Divergence confirmed: price and CVD trending in opposite directions
                           AND |Z-score| > CVD_EXIT_ZSCORE (2.0)

WHY EMA as Kalman proxy:
A proper Kalman filter requires tuning noise covariance matrices.
EMA with α=0.15 approximates the same smoothing behaviour with
zero parameter risk — safe for a solo developer building phase by phase.

Output: CVDSignal
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from data.schema import OHLCV

CVD_EMA_ALPHA = 0.15   # Smoothing factor — lower = smoother, slower
CVD_EXIT_ZSCORE = 2.0  # Z-score threshold for confirmed divergence


@dataclass(frozen=True)
class CVDSignal:
    divergence_confirmed: bool
    z_score:              float
    direction:            str    # Direction the divergence implies: "LONG" | "SHORT"
    trend_aligned:        bool   # CVD and price both moving the same way


def detect_cvd_divergence(
    cvd_history: list[float],
    m1_bars:     list[OHLCV],
) -> CVDSignal:
    """
    Detect price/CVD divergence.

    Args:
        cvd_history: Per-minute CVD values (from CVDEngine), oldest-first
        m1_bars:     M1 OHLCV bars (oldest-first)

    Returns:
        CVDSignal
    """
    if len(cvd_history) < 20 or len(m1_bars) < 11:
        return CVDSignal(
            divergence_confirmed=False,
            z_score=0.0,
            direction="LONG",
            trend_aligned=False,
        )

    # ── Step 1: EMA-smooth CVD history ───────────────────────────────────
    smoothed = _ema_smooth(cvd_history, CVD_EMA_ALPHA)

    # ── Step 2: Residuals ─────────────────────────────────────────────────
    residuals = [c - s for c, s in zip(cvd_history, smoothed)]

    # ── Step 3: Z-score of most recent residual ───────────────────────────
    recent_residuals = residuals[-20:]
    mean_r = sum(recent_residuals) / len(recent_residuals)
    var_r  = sum((r - mean_r) ** 2 for r in recent_residuals) / len(recent_residuals)
    std_r  = math.sqrt(var_r) if var_r > 0 else 1e-9
    z      = residuals[-1] / std_r

    # ── Step 4: Price trend ───────────────────────────────────────────────
    price_now  = m1_bars[-1].close
    price_10   = m1_bars[-11].close   # 10 bars ago
    price_up   = price_now > price_10

    # ── Step 5: CVD trend ─────────────────────────────────────────────────
    cvd_now  = cvd_history[-1]
    cvd_10   = cvd_history[-11]
    cvd_up   = cvd_now > cvd_10

    # ── Step 6: Divergence classification ────────────────────────────────
    bearish_div = price_up  and not cvd_up   # Price up, CVD down → sell pressure
    bullish_div = not price_up and cvd_up    # Price down, CVD up → buy pressure

    divergence        = bearish_div or bullish_div
    divergence_conf   = divergence and abs(z) > CVD_EXIT_ZSCORE

    if bearish_div:
        implied_dir = "SHORT"
    elif bullish_div:
        implied_dir = "LONG"
    else:
        implied_dir = "LONG" if price_up else "SHORT"

    trend_aligned = (price_up and cvd_up) or (not price_up and not cvd_up)

    return CVDSignal(
        divergence_confirmed=divergence_conf,
        z_score=z,
        direction=implied_dir,
        trend_aligned=trend_aligned,
    )


def _ema_smooth(values: list[float], alpha: float) -> list[float]:
    """Apply EMA smoothing to a series. Returns same-length smoothed series."""
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed

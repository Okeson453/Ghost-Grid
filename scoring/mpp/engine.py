"""
scoring/mpp/engine.py
MPP Strategy 3 coordinator — Institutional Footprint.

Scoring rubric:
  CVD divergence:    max 25 pts  (Z-score + directional alignment)
  Session bias:      max 20 pts  (VWAP + bar consistency)
  Absorption:        max 15 pts  (sweep-and-reclaim, HV rejection)

Total possible: 60 (no cap needed — rubric sums to exactly 60)
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from scoring.models import MPPResult
from scoring.mpp.cvd_divergence import detect_cvd_divergence
from scoring.mpp.session_bias   import compute_session_bias, score_session_bias
from scoring.mpp.absorption     import detect_absorption, score_absorption


def calculate_mpp(snap: MarketSnapshot, direction: str) -> MPPResult:
    """
    Calculate MPP score for given direction.

    Args:
        snap:      Full MarketSnapshot (requires cvd_history, m1, vwap, session)
        direction: "LONG" | "SHORT"

    Returns:
        MPPResult with score 0–60
    """
    # ── CVD divergence ────────────────────────────────────────────────────
    cvd = detect_cvd_divergence(snap.cvd_history, snap.m1)

    if cvd.divergence_confirmed and cvd.direction == direction:
        # Divergence confirms our direction → maximum CVD score
        cvd_pts = 25
    elif cvd.trend_aligned:
        # CVD and price both moving in direction → partial confirmation
        cvd_pts = 12
    else:
        cvd_pts = 0

    # ── Session bias ──────────────────────────────────────────────────────
    bias     = compute_session_bias(
        snap.m1, snap.vwap, snap.tick.mid, direction
    )
    bias_pts = score_session_bias(bias)

    # ── Absorption ────────────────────────────────────────────────────────
    absorption = detect_absorption(snap.m1, direction)
    abs_pts    = score_absorption(absorption)

    total = min(cvd_pts + bias_pts + abs_pts, 60)

    return MPPResult(score=total, direction=direction)

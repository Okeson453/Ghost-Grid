"""
scoring/hmp/engine.py
HMP Strategy 1 — Smart Money Structure Detection.

SOURCE: GHOST-GRID-MT5-Design.md § III.3.1 HMP: Price Action

Evaluates institutional footprint through 4 price action components:

BOS (Break of Structure):
  - max 20 pts (20 if momentum > 0.70, 10 if ≤ 0.70, -8 if MTF unaligned)
  - Detects directional conviction when price violates prior swing

CHoCH (Change of Character):
  - max 15 pts (15 if high quality, 8 if medium, 0 if low/none)
  - Confirms mood shift when momentum reverses mid-trend

FVG (Fair Value Gap):
  - max 15 pts (15 if distance < 0.5 ATR, 7 if found but further)
  - Marks imbalance for reversal setup

Order Block:
  - max 10 pts (10 if fresh + imbalance > 0.6, 4 if found, 0 if stale)
  - Identifies accumulation/distribution zones

Total possible: 60 pts (capped)
Direction determined by dominant signal (BOS takes precedence if conflicting).
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from scoring.models import HMPResult, BOSResult, CHoCHResult, FVGResult, OrderBlockResult
from scoring.hmp.bos import detect_bos
from scoring.hmp.choch import detect_choch
from scoring.hmp.fvg import find_nearest_fvg
from scoring.hmp.order_block import find_active_ob


def calculate_hmp(snap: MarketSnapshot, direction: str) -> HMPResult:
    """
    Calculate HMP score for given direction.

    Args:
        snap:      Full MarketSnapshot (requires m3, m5, atr_5m, tick)
        direction: "LONG" | "SHORT" — the direction being scored

    Returns:
        HMPResult with score 0–60 and sub-component details
    """
    current_price = snap.tick.mid

    # ── Break of Structure ───────────────────────────────────────────────
    bos = detect_bos(snap.m5, snap.m3, direction, snap.atr_5m)

    if bos.confirmed:
        if bos.momentum > 0.70:
            bos_pts = 20
        else:
            bos_pts = 10
        if not bos.mtf_aligned:
            bos_pts = max(0, bos_pts - 8)
    else:
        bos_pts = 0

    # ── Change of Character ──────────────────────────────────────────────
    choch = detect_choch(snap.m3, snap.m5, direction)

    if choch.quality == "high":
        choch_pts = 15
    elif choch.quality == "med":
        choch_pts = 8
    else:
        choch_pts = 0

    # ── Fair Value Gap ───────────────────────────────────────────────────
    fvg = find_nearest_fvg(snap.m3, current_price, snap.atr_5m, direction)

    if fvg.found and fvg.unfilled:
        if fvg.distance_pct < 0.5:
            fvg_pts = 15
        elif fvg.distance_pct < 1.5:
            fvg_pts = 7
        else:
            fvg_pts = 0
    else:
        fvg_pts = 0
        fvg = FVGResult(
            found=False, top=0.0, bottom=0.0, gap_size=0.0,
            unfilled=False, distance_pct=999.0, direction="NONE"
        )

    # ── Order Block ──────────────────────────────────────────────────────
    ob = find_active_ob(snap.m5, current_price, direction)

    if ob.found:
        if not ob.stale and ob.imbalance_ratio > 0.6:
            ob_pts = 10
        else:
            ob_pts = 4
    else:
        ob_pts = 0

    # ── Score aggregation ───────────────────────────────────────────────
    total_score = min(60, bos_pts + choch_pts + fvg_pts + ob_pts)

    return HMPResult(
        score=total_score,
        direction=direction,
        bos=bos,
        choch=choch,
        fvg=fvg if fvg.found else None,
        order_block=ob if ob.found else None,
        bos_pts=bos_pts,
        choch_pts=choch_pts,
        fvg_pts=fvg_pts,
        ob_pts=ob_pts,
    )

"""
scoring/fusion.py
H_c = HMP + HLCP + MPP  ·  Range: 0–180  ·  Direction: LONG | SHORT

Fusion algorithm:
  1. Score LONG direction across all three strategies
  2. Score SHORT direction across all three strategies
  3. The direction with the higher composite H_c wins
  4. H_c is the winning direction's composite score, capped at 180

WHY score both directions and pick the winner:
Scoring only one direction risks missing a high-conviction SHORT
when the operator assumed LONG from session bias alone.
Both directions are always evaluated; the market picks.

Called by: main.py scoring pipeline coroutine (once per MarketSnapshot)
"""

from __future__ import annotations
import time
from data.schema import MarketSnapshot
from scoring.models import ConfluenceScore, HMPResult, HLCPResult, MPPResult
from scoring.hmp.engine import calculate_hmp
from scoring.hlcp.engine import calculate_hlcp
from scoring.mpp.engine import calculate_mpp


def score_confluence(snap: MarketSnapshot) -> ConfluenceScore:
    """
    Compute full H_c score for both directions; return the winning score.

    Args:
        snap: Full MarketSnapshot with regime populated

    Returns:
        ConfluenceScore — best direction with 0–180 composite
    """
    # Score LONG
    hmp_long = calculate_hmp(snap, "LONG")
    hlcp_long = calculate_hlcp(snap, "LONG")
    mpp_long = calculate_mpp(snap, "LONG")
    long_composite = min(hmp_long.score + hlcp_long.score + mpp_long.score, 180)

    # Score SHORT
    hmp_short = calculate_hmp(snap, "SHORT")
    hlcp_short = calculate_hlcp(snap, "SHORT")
    mpp_short = calculate_mpp(snap, "SHORT")
    short_composite = min(hmp_short.score + hlcp_short.score + mpp_short.score, 180)

    # Pick winner
    if long_composite >= short_composite:
        direction = "LONG"
        composite = long_composite
        hmp, hlcp, mpp = hmp_long, hlcp_long, mpp_long
    else:
        direction = "SHORT"
        composite = short_composite
        hmp, hlcp, mpp = hmp_short, hlcp_short, mpp_short

    return ConfluenceScore(
        symbol=snap.symbol,
        hmp=hmp.score,
        hlcp=hlcp.score,
        mpp=mpp.score,
        composite=composite,
        direction=direction,
        regime=snap.regime,
        session=snap.session,
        timestamp_ms=snap.tick.timestamp_ms,
    )

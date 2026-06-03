"""
scoring/hlcp/engine.py
HLCP Strategy 2 coordinator — Trend + Liquidity Intelligence.

Scoring rubric:
  Trend alignment:    max 25 pts  (EMA ribbon consensus + slope)
  Liquidity void:     max 20 pts  (equal high/low distance)
  Momentum decay:     max 15 pts  (RSI(7) extreme + volume cliff)
  Kill-zone bonus:      5 pts     (London / NY Overlap session)

Total possible: 65 → capped at 60.
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from scoring.models import HLCPResult
from regime.indicators.ema_ribbon import EMARibbonCalculator
from scoring.hlcp.trend_alignment  import score_trend_alignment
from scoring.hlcp.liquidity_mapper import map_liquidity, score_liquidity
from scoring.hlcp.momentum_decay   import detect_momentum_decay, score_momentum_decay
from scoring.hlcp.killzone         import score_killzone

# Per-symbol ribbon calculators (state maintained between snapshots)
_ribbon_calculators: dict[str, EMARibbonCalculator] = {}


def calculate_hlcp(snap: MarketSnapshot, direction: str) -> HLCPResult:
    """
    Calculate HLCP score for given direction.

    Args:
        snap:      Full MarketSnapshot (requires m1, m5, atr_1m, atr_5m, session)
        direction: "LONG" | "SHORT"

    Returns:
        HLCPResult with score 0–60
    """
    # ── EMA ribbon ───────────────────────────────────────────────────────
    ribbon_calc = _get_ribbon(snap.symbol)
    ribbon      = ribbon_calc.update(snap.m1[-1], snap.atr_1m) if snap.m1 else None

    trend_pts = score_trend_alignment(ribbon, direction) if ribbon else 0

    # ── Liquidity void ───────────────────────────────────────────────────
    liq_map  = map_liquidity(snap.m5, snap.tick.mid, snap.atr_5m, direction)
    liq_pts  = score_liquidity(liq_map)

    # ── Momentum decay ───────────────────────────────────────────────────
    decay     = detect_momentum_decay(snap.m1, direction)
    decay_pts = score_momentum_decay(decay)

    # ── Kill-zone bonus ──────────────────────────────────────────────────
    kz_pts = score_killzone(snap.session)

    total = min(trend_pts + liq_pts + decay_pts + kz_pts, 60)

    return HLCPResult(score=total, direction=direction)


def _get_ribbon(symbol: str) -> EMARibbonCalculator:
    if symbol not in _ribbon_calculators:
        _ribbon_calculators[symbol] = EMARibbonCalculator()
    return _ribbon_calculators[symbol]

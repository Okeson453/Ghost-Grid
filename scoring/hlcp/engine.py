"""
scoring/hlcp/engine.py
HLCP Strategy 2 — Trend + Liquidity Intelligence.

SOURCE: GHOST-GRID-MT5-Design.md § III.3.2 HLCP: Confluence & Flow

Evaluates macro confluence and liquidity imbalances through 4 components:

Trend Alignment:
  - max 25 pts (EMA ribbon consensus, slope strength, session kill-zone bonus +5)
  - 8/13/21/34-period EMA ribbon must be fanned (not compressed)
  - Higher slope = stronger conviction
  - London/NY overlap adds +5 pts (institutional activity hours)

Liquidity Mapping:
  - max 20 pts (equal highs/lows, unfilled FVG zones)
  - Identifies price levels where smart money is likely watching
  - ATR-normalized distance prevents false signals in volatile markets

Momentum Decay:
  - max 15 pts (RSI(7) extreme + volume cliff + divergence)
  - Detects exhaustion before reversal
  - All three signals must align for full points

Kill-zone Session Bonus:
  - +5 pts during London/NY overlap (high institutional activity)

Total: 65 → capped at 60 pts
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from scoring.models import HLCPResult
from regime.indicators.ema_ribbon import EMARibbonCalculator
from scoring.hlcp.trend_alignment import score_trend_alignment
from scoring.hlcp.liquidity_mapper import map_liquidity, score_liquidity
from scoring.hlcp.momentum_decay import detect_momentum_decay, score_momentum_decay
from scoring.hlcp.killzone import score_killzone

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
    ribbon = ribbon_calc.update(snap.m1[-1], snap.atr_1m) if snap.m1 else None

    trend_pts = score_trend_alignment(ribbon, direction) if ribbon else 0

    # ── Liquidity void ───────────────────────────────────────────────────
    liq_map = map_liquidity(snap.m5, snap.tick.mid, snap.atr_5m, direction)
    liq_pts = score_liquidity(liq_map)

    # ── Momentum decay ───────────────────────────────────────────────────
    decay = detect_momentum_decay(snap.m1, direction)
    decay_pts = score_momentum_decay(decay)

    # ── Kill-zone bonus ──────────────────────────────────────────────────
    kz_pts = score_killzone(snap.session)

    total = min(trend_pts + liq_pts + decay_pts + kz_pts, 60)

    return HLCPResult(
        score=total,
        direction=direction,
        trend_pts=trend_pts,
        liquidity_pts=liq_pts,
        momentum_pts=decay_pts,
        killzone_pts=kz_pts,
    )


def _get_ribbon(symbol: str) -> EMARibbonCalculator:
    if symbol not in _ribbon_calculators:
        _ribbon_calculators[symbol] = EMARibbonCalculator()
    return _ribbon_calculators[symbol]

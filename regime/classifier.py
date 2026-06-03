"""
regime/classifier.py
4-state market regime classifier.

States:
  TREND     → Strong directional move; ATR expanding; EMA ribbon fanned
  CHOP      → ATR contracting; price oscillating; no EMA separation
  BREAKOUT  → Recent structure break; volume spike; spread widening
  REVERSAL  → Momentum exhaustion; BOS + CHoCH confirmed against prior trend

Algorithm:
  Uses 4 indicators — all available from MT5 data alone:
    1. ATR ratio (1m/5m)       → volatility state
    2. EMA ribbon separation   → trend strength
    3. Volume ratio            → activity level
    4. Recent BOS flag         → structural break present?

Decision is rule-based (not ML in Phase 3). ML HMM is deferred to Phase 2+ post-live.

WHY rule-based: avoids data starvation problem. HMM requires 500+ labelled
transitions before it generalises. Rule-based gives consistent, debuggable
behaviour from day one.
"""

from __future__ import annotations
import logging
from data.schema import MarketSnapshot
from regime.indicators.ema_ribbon import EMARibbonCalculator
from regime.indicators.atr_ratio import compute_atr_ratio
from regime.indicators.volume_profile import compute_volume_ratio

logger = logging.getLogger(__name__)

# One calculator per symbol — maintained in fingerprint.py
_ribbon_cache: dict[str, EMARibbonCalculator] = {}


def classify_regime(snap: MarketSnapshot) -> str:
    """
    Classify current market regime for one symbol.

    Returns one of: "TREND" | "CHOP" | "BREAKOUT" | "REVERSAL"

    WHY default to CHOP: conservative bias. When signals are ambiguous,
    require higher H_c threshold (155) rather than lower (130).
    This prevents entering poor-quality setups during uncertain conditions.
    """
    if not snap.m1 or len(snap.m1) < 34:
        return "CHOP"  # Insufficient data → conservative default

    # ── Compute indicators ───────────────────────────────────────────────

    # EMA ribbon
    ribbon_calc = _get_ribbon(snap.symbol)
    ribbon_state = ribbon_calc.update(snap.m1[-1], snap.atr_1m)
    if ribbon_state is None:
        return "CHOP"

    # ATR ratio
    atr_ratio = compute_atr_ratio(snap.atr_1m, snap.atr_5m)

    # Volume ratio (M1 last 5 bars)
    vol_ratio = compute_volume_ratio(snap.m1, lookback=5)

    # RSI(7) on M1 for exhaustion check
    rsi_7 = _rsi(snap.m1, 7)

    # ── Classification rules ─────────────────────────────────────────────

    # BREAKOUT: volume spike + ATR expanding + recent bar has large body
    last_m1 = snap.m1[-1]
    large_body = last_m1.body > snap.atr_1m * 0.8
    if vol_ratio > 2.0 and atr_ratio > 1.05 and large_body:
        return "BREAKOUT"

    # REVERSAL: momentum exhaustion + RSI extreme + EMA overextension
    ema_overextended = ribbon_state.separation > snap.atr_1m * 3.0
    rsi_extreme      = rsi_7 > 75 or rsi_7 < 25
    if rsi_extreme and ema_overextended and vol_ratio < 1.5:
        return "REVERSAL"

    # TREND: EMA fanned + ATR neutral/expanding + direction consistency
    if ribbon_state.is_fanned() and ribbon_state.slope_strength > 0.40 and atr_ratio > 0.95:
        return "TREND"

    # CHOP: EMA flat + ATR contracting + low volume
    if not ribbon_state.is_fanned() and atr_ratio < 1.0 and vol_ratio < 1.3:
        return "CHOP"

    # Default: CHOP (conservative)
    return "CHOP"


def _get_ribbon(symbol: str) -> EMARibbonCalculator:
    """Get or create EMA ribbon calculator for symbol."""
    if symbol not in _ribbon_cache:
        _ribbon_cache[symbol] = EMARibbonCalculator()
    return _ribbon_cache[symbol]


def _rsi(bars: list, period: int) -> float:
    """
    Lightweight RSI calculation.
    WHY inline: avoids TA-Lib dependency in the regime module.
    Regime module must be fast and dependency-light.
    """
    if len(bars) < period + 1:
        return 50.0  # Neutral default

    closes = [b.close for b in bars[-(period + 1):]]
    gains, losses = [], []

    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

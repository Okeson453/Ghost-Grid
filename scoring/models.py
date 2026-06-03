"""
scoring/models.py
Shared data models for the H_c scoring engine.

All scoring sub-systems return dataclasses defined here.
No scoring logic in this file — pure data containers.

Import hierarchy: scoring/models.py imports only from data/schema.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Gate decisions ────────────────────────────────────────────────────────

class GateDecision(str, Enum):
    """Gate decision enum for confluence score routing."""
    DISCARD = "DISCARD"  # H_c too low — no action
    WATCHLIST = "WATCHLIST"  # Approaching threshold — pre-warm
    ALERT = "ALERT"  # At threshold, 1 cycle — Telegram only
    FULL_AUTO = "FULL_AUTO"  # At threshold, ≥2 cycles — execute
    FULL_AUTO_STRONG = "FULL_AUTO_STRONG"  # H_c ≥ threshold + 20 — max size


# ── Direction ─────────────────────────────────────────────────────────────

class Direction(str, Enum):
    """Trade direction enum."""
    LONG = "LONG"
    SHORT = "SHORT"


# ── HMP sub-detector results ──────────────────────────────────────────────

@dataclass(frozen=True)
class SwingPoint:
    """A detected swing high or swing low."""
    price: float
    timestamp_ms: int
    swing_type: str  # "HIGH" | "LOW"
    bar_index: int  # Index in the bars list (negative = from end)


@dataclass(frozen=True)
class BOSResult:
    """Break of Structure detection result."""
    confirmed: bool
    momentum: float  # |close - swing| / ATR(14), 0.0 if not confirmed
    swing_level: float  # The broken swing level
    mtf_aligned: bool  # M3 confirms M5 BOS in same direction

    @property
    def score_contribution(self) -> int:
        """
        WHY: score is computed inside engine.py, not here.
        This property is for quick diagnostic logging only.
        """
        if not self.confirmed:
            return 0
        base = 20 if self.momentum > 0.70 else 10
        penalty = -8 if not self.mtf_aligned else 0
        return max(0, base + penalty)


@dataclass(frozen=True)
class CHoCHResult:
    """Change of Character detection result."""
    confirmed: bool
    quality: str  # "high" | "med" | "low" | "none"
    level: float  # Price level where CHoCH occurred


@dataclass(frozen=True)
class FVGResult:
    """Fair Value Gap detection result."""
    found: bool
    top: float
    bottom: float
    gap_size: float  # top - bottom in price units
    unfilled: bool  # True if price hasn't re-entered the gap
    distance_pct: float  # |current_price - gap_boundary| / ATR_5m
    direction: str  # "BULLISH" | "BEARISH" | "NONE"


@dataclass(frozen=True)
class OrderBlockResult:
    """Order Block detection result."""
    found: bool
    top: float
    bottom: float
    test_count: int  # How many times price has tested this zone
    imbalance_ratio: float  # Buy vs sell volume imbalance at OB creation
    stale: bool  # True if OB has been tested ≥3 times


# ── Full HMP result ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class HMPResult:
    """Complete HMP (Smart Money Structure) scoring result."""
    score: int  # 0–60
    direction: str  # "LONG" | "SHORT"
    bos: BOSResult
    choch: CHoCHResult
    fvg: Optional[FVGResult]
    order_block: Optional[OrderBlockResult]

    # Score breakdown for logging/debugging
    bos_pts: int = 0
    choch_pts: int = 0
    fvg_pts: int = 0
    ob_pts: int = 0


# ── Confluence score (assembled in Part 4: scoring/fusion.py) ─────────────

@dataclass(frozen=True)
class ConfluenceScore:
    """
    Final H_c score for one scoring cycle.
    Produced by scoring/fusion.py (Part 4).
    HMP available after Part 2; HLCP + MPP added in Part 3.
    """
    symbol: str
    hmp: int  # 0–60
    hlcp: int  # 0–60 (0 until Part 3 is merged)
    mpp: int  # 0–60 (0 until Part 3 is merged)
    composite: int  # hmp + hlcp + mpp, capped at 180
    direction: str  # "LONG" | "SHORT"
    regime: str  # "" until Part 3 is merged
    session: str
    timestamp_ms: int

    @property
    def above_threshold(self) -> bool:
        """Convenience check used by gate.py."""
        from config.constants import REGIME_THRESHOLDS
        threshold = REGIME_THRESHOLDS.get(self.regime, 140)
        return self.composite >= threshold


# ── HLCP result (stub — filled in Part 3) ─────────────────────────────────

@dataclass(frozen=True)
class HLCPResult:
    """Trend + Liquidity scoring result. Filled in Part 3."""
    score: int = 0
    direction: str = "LONG"


# ── MPP result (stub — filled in Part 3) ──────────────────────────────────

@dataclass(frozen=True)
class MPPResult:
    """Institutional Footprint scoring result. Filled in Part 3."""
    score: int = 0
    direction: str = "LONG"

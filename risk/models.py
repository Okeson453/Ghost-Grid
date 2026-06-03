"""
risk/models.py
Data models for the risk governor layer.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProposedOrder:
    """
    An order candidate passed to the RiskGovernor for validation.
    Constructed by main.py scoring pipeline after FULL_AUTO gate decision.
    """
    symbol:        str
    direction:     str      # "LONG" | "SHORT"
    entry_price:   float    # Current ask (LONG) or bid (SHORT)
    stop_loss:     float    # ATR-based stop (computed externally)
    atr_5m:        float    # Current ATR_5m (used for RR check)
    spread_pct:    float    # Current spread as fraction of price
    hc_score:      int      # H_c at time of proposal
    regime:        str      # Regime at time of proposal
    session:       str      # Session at time of proposal

    @property
    def pip_risk(self) -> float:
        """Absolute price distance to stop loss."""
        return abs(self.entry_price - self.stop_loss)

    @property
    def rr_ratio(self) -> float:
        """
        Reward:Risk ratio.
        Target = entry + (pip_risk × 1.5) → natural 1.5R target.
        """
        return self.atr_5m / self.pip_risk if self.pip_risk > 0 else 0.0


@dataclass(frozen=True)
class PortfolioSnapshot:
    """
    Current portfolio state — passed to RiskGovernor for basket checks.
    Populated by portfolio/state.py.
    """
    net_equity:           float
    starting_equity:      float   # Equity at UTC midnight (daily loss reference)
    daily_pnl:            float   # Realised + unrealised since midnight
    open_position_count:  int
    total_basket_risk:    float   # Sum of all open position risk in USD
    margin_utilisation:   float   # 0.0–1.0 fraction of available margin used
    day_locked:           bool    # True if daily loss limit already triggered


@dataclass(frozen=True)
class ValidationResult:
    approved:   bool
    reason:     Optional[str]     # None if approved; human-readable reason if rejected
    lot_size:   Optional[float]   # None if rejected; computed lot size if approved

    @property
    def rejected(self) -> bool:
        return not self.approved

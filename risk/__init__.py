"""
risk/
Risk governance layer for GHOST GRID.

Public API:
  RiskGovernor          — Main validator class
  ProposedOrder         — Order candidate for validation
  PortfolioSnapshot     — Portfolio state for validation
  ValidationResult      — Approval/rejection result with lot size

  All risk constants are immutable and hardcoded:
  MAX_RISK_PER_TRADE, MAX_DAILY_LOSS, MAX_DAILY_GAIN, etc.
"""

from .governor import RiskGovernor
from .models import ProposedOrder, PortfolioSnapshot, ValidationResult
from .constants import (
    MAX_RISK_PER_TRADE,
    MIN_RR_RATIO,
    MAX_CONCURRENT,
    MAX_BASKET_RISK,
    MAX_PORTFOLIO_DRAWDOWN,
    MAX_DAILY_LOSS,
    MAX_DAILY_GAIN,
    MAX_SPREAD_PCT,
    MARGIN_BUFFER,
    MIN_LOT_SIZE,
    MAX_LOT_SIZE,
)

__all__ = [
    "RiskGovernor",
    "ProposedOrder",
    "PortfolioSnapshot",
    "ValidationResult",
    "MAX_RISK_PER_TRADE",
    "MIN_RR_RATIO",
    "MAX_CONCURRENT",
    "MAX_BASKET_RISK",
    "MAX_PORTFOLIO_DRAWDOWN",
    "MAX_DAILY_LOSS",
    "MAX_DAILY_GAIN",
    "MAX_SPREAD_PCT",
    "MARGIN_BUFFER",
    "MIN_LOT_SIZE",
    "MAX_LOT_SIZE",
]

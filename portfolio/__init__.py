"""
portfolio/__init__.py
Portfolio state management, PnL tracking, equity monitoring, and mode automation.
"""

from __future__ import annotations

from portfolio.state import PortfolioState, FrozenPortfolioSnapshot
from portfolio.ledger import Ledger
from portfolio.equity_tracker import EquityTracker, EquityRecord
from portfolio.correlation import CorrelationEngine, calculate_correlation
from portfolio.mode_automaton import ModeDecision, select_mode

__all__ = [
    "PortfolioState",
    "FrozenPortfolioSnapshot",
    "Ledger",
    "EquityTracker",
    "EquityRecord",
    "CorrelationEngine",
    "calculate_correlation",
    "ModeDecision",
    "select_mode",
]

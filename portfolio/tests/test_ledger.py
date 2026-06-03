"""
tests/portfolio/test_ledger.py
Unit tests for portfolio/ledger.py
"""

import pytest
from portfolio.state import PortfolioState
from portfolio.ledger import Ledger


class TestLedger:
    """Test suite for Ledger class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ledger = Ledger()
        self.state = PortfolioState(
            starting_equity=10_000.0,
            net_equity=10_000.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
        )

    def test_record_close_positive_pnl(self):
        """Test recording a positive closed trade."""
        self.ledger.record_close(self.state, 100.0)
        assert self.state.realized_pnl == 100.0

    def test_record_close_negative_pnl(self):
        """Test recording a negative closed trade."""
        self.ledger.record_close(self.state, -50.0)
        assert self.state.realized_pnl == -50.0

    def test_record_close_multiple(self):
        """Test recording multiple closes accumulates."""
        self.ledger.record_close(self.state, 100.0)
        self.ledger.record_close(self.state, 50.0)
        self.ledger.record_close(self.state, -25.0)
        assert self.state.realized_pnl == 125.0

    def test_reset_daily(self):
        """Test daily reset."""
        self.state.realized_pnl = 50.0
        self.state.unrealized_pnl = -20.0
        self.state.day_locked = True
        self.state.nuclear_count_today = 2

        self.ledger.reset_daily(self.state, 10_050.0)

        assert self.state.starting_equity == 10_050.0
        assert self.state.realized_pnl == 0.0
        assert self.state.unrealized_pnl == 0.0
        assert self.state.day_locked is False
        assert self.state.nuclear_count_today == 0

    def test_update_unrealized_empty_positions(self):
        """Test unrealized update with no positions."""
        self.ledger.update_unrealized(self.state, {"EURUSD": 1.0850})
        assert self.state.unrealized_pnl == 0.0

    def test_get_daily_metrics(self):
        """Test daily metrics calculation."""
        self.state.realized_pnl = 100.0
        self.state.unrealized_pnl = -50.0
        self.state.net_equity = 10_050.0

        metrics = self.ledger.get_daily_metrics(self.state)

        assert metrics["daily_pnl"] == 50.0
        assert metrics["realized_pnl"] == 100.0
        assert metrics["unrealized_pnl"] == -50.0
        assert metrics["net_equity"] == 10_050.0
        assert abs(metrics["daily_pnl_pct"] - 0.005) < 0.0001

    def test_daily_pnl_property(self):
        """Test daily PnL property."""
        self.state.realized_pnl = 100.0
        self.state.unrealized_pnl = 50.0
        assert self.state.daily_pnl == 150.0

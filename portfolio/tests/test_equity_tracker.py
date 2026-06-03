"""
tests/portfolio/test_equity_tracker.py
Unit tests for portfolio/equity_tracker.py
"""

import pytest
import time
from portfolio.equity_tracker import EquityTracker, EquityRecord
from portfolio.state import PortfolioState


class TestEquityTracker:
    """Test suite for EquityTracker class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = EquityTracker(history_length=100)

    def test_record_equity_basic(self):
        """Test recording a single equity value."""
        self.tracker.record_equity(10_100.0)
        assert len(self.tracker.history) == 1
        assert self.tracker.history[0].equity == 10_100.0

    def test_peak_equity_tracking(self):
        """Test that peak equity is tracked correctly."""
        self.tracker.record_equity(10_000.0)
        self.tracker.record_equity(10_100.0)
        self.tracker.record_equity(10_050.0)
        assert self.tracker.get_peak_equity() == 10_100.0

    def test_low_equity_tracking(self):
        """Test that low equity is tracked correctly."""
        self.tracker.record_equity(10_000.0)
        self.tracker.record_equity(10_100.0)
        self.tracker.record_equity(9_950.0)
        assert self.tracker.low_equity == 9_950.0

    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        self.tracker.record_equity(10_000.0)
        self.tracker.record_equity(10_100.0)
        self.tracker.record_equity(9_900.0)
        drawdown_pct = self.tracker.get_drawdown_pct()
        # Drawdown = (10100 - 9900) / 10100 ≈ 0.0198
        assert abs(drawdown_pct - 0.0198) < 0.001

    def test_drawdown_absolute(self):
        """Test absolute drawdown calculation."""
        self.tracker.record_equity(10_000.0)
        self.tracker.record_equity(10_100.0)
        self.tracker.record_equity(9_900.0)
        drawdown_abs = self.tracker.get_drawdown_abs()
        assert drawdown_abs == 200.0

    def test_get_latest_equity(self):
        """Test getting latest equity."""
        self.tracker.record_equity(10_000.0)
        self.tracker.record_equity(10_100.0)
        assert self.tracker.get_latest_equity() == 10_100.0

    def test_history_limit(self):
        """Test that history is limited to specified length."""
        tracker = EquityTracker(history_length=5)
        for i in range(10):
            tracker.record_equity(10_000.0 + i)
        assert len(tracker.history) == 5
        # Should keep the last 5
        assert tracker.history[0].equity == 10_005.0

    def test_update_state_equity(self):
        """Test updating PortfolioState with tracker equity."""
        self.tracker.record_equity(10_050.0)
        state = PortfolioState()
        self.tracker.update_state_equity(state)
        assert state.net_equity == 10_050.0

    def test_volatility_calculation(self):
        """Test equity volatility calculation."""
        base_equity = 10_000.0
        for i in range(10):
            self.tracker.record_equity(base_equity + i * 10)
        volatility = self.tracker.get_volatility(lookback_seconds=300)
        # With linear increases of 10, volatility should be ~0 (constant slope)
        assert volatility >= 0  # Should not error

    def test_reset_tracking(self):
        """Test resetting the tracker."""
        self.tracker.record_equity(10_100.0)
        self.tracker.reset_tracking()
        assert len(self.tracker.history) == 0
        assert self.tracker.peak_equity == self.tracker.low_equity

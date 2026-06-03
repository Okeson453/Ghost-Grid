"""
tests/portfolio/test_correlation.py
Unit tests for portfolio/correlation.py
"""

import pytest
from portfolio.correlation import CorrelationEngine, calculate_correlation
from portfolio.state import PortfolioState


class TestCalculateCorrelation:
    """Test suite for calculate_correlation function."""

    def test_perfect_positive_correlation(self):
        """Test perfect positive correlation."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr = calculate_correlation(values1, values2)
        assert corr is not None
        assert abs(corr - 1.0) < 0.0001

    def test_perfect_negative_correlation(self):
        """Test perfect negative correlation."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [5.0, 4.0, 3.0, 2.0, 1.0]
        corr = calculate_correlation(values1, values2)
        assert corr is not None
        assert abs(corr - (-1.0)) < 0.0001

    def test_no_correlation(self):
        """Test no correlation."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [3.0, 1.0, 4.0, 1.0, 5.0]
        corr = calculate_correlation(values1, values2)
        assert corr is not None
        # Should be close to 0
        assert abs(corr) < 0.5

    def test_insufficient_data(self):
        """Test that function returns None for insufficient data."""
        values1 = [1.0]
        values2 = [2.0]
        corr = calculate_correlation(values1, values2)
        assert corr is None

    def test_different_lengths(self):
        """Test that function returns None for different length arrays."""
        values1 = [1.0, 2.0, 3.0]
        values2 = [2.0, 4.0]
        corr = calculate_correlation(values1, values2)
        assert corr is None

    def test_zero_variance(self):
        """Test correlation with zero variance."""
        values1 = [1.0, 1.0, 1.0, 1.0]
        values2 = [2.0, 3.0, 4.0, 5.0]
        corr = calculate_correlation(values1, values2)
        assert corr is None


class TestCorrelationEngine:
    """Test suite for CorrelationEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = CorrelationEngine(window_size=10)

    def test_record_price(self):
        """Test recording prices."""
        self.engine.record_price("EURUSD", 1.0850)
        self.engine.record_price("EURUSD", 1.0851)
        assert len(self.engine.price_windows["EURUSD"]) == 2

    def test_window_size_limit(self):
        """Test that window size is limited."""
        for i in range(20):
            self.engine.record_price("EURUSD", 1.0800 + i * 0.0001)
        assert len(self.engine.price_windows["EURUSD"]) == 10

    def test_compute_correlation_empty_positions(self):
        """Test correlation computation with no positions."""
        state = PortfolioState()
        corr = self.engine.compute_portfolio_correlation(state)
        assert corr == 0.0

    def test_compute_correlation_single_position(self):
        """Test correlation computation with only one position."""
        state = PortfolioState()
        # Mock position
        class MockPosition:
            symbol = "EURUSD"
        state.add_position(1, MockPosition())
        corr = self.engine.compute_portfolio_correlation(state)
        assert corr == 0.0

    def test_update_state(self):
        """Test state update."""
        state = PortfolioState()
        self.engine.record_price("EURUSD", 1.0850)
        self.engine.update_state(state)
        assert state.avg_pair_correlation >= 0.0

    def test_is_high_correlation(self):
        """Test high correlation detection."""
        state = PortfolioState()
        state.avg_pair_correlation = 0.5
        assert self.engine.is_high_correlation(state) is False
        
        state.avg_pair_correlation = 0.9
        assert self.engine.is_high_correlation(state) is True

    def test_reset(self):
        """Test resetting the engine."""
        self.engine.record_price("EURUSD", 1.0850)
        self.engine.record_price("GBPUSD", 1.2700)
        self.engine.reset()
        assert len(self.engine.price_windows) == 0

"""
tests/portfolio/test_state.py
Unit tests for PortfolioState and FrozenPortfolioSnapshot.
"""

import pytest
from portfolio.state import PortfolioState, FrozenPortfolioSnapshot


class TestPortfolioState:
    """Test PortfolioState initialization and properties."""

    def test_default_initialization(self):
        """Default initialization values."""
        state = PortfolioState()
        assert state.starting_equity == 10_000.0
        assert state.net_equity == 10_000.0
        assert state.realized_pnl == 0.0
        assert state.unrealized_pnl == 0.0
        assert state.daily_pnl == 0.0

    def test_daily_pnl_property(self):
        """Daily PnL = realized + unrealized."""
        state = PortfolioState()
        state.realized_pnl = 100.0
        state.unrealized_pnl = 50.0
        assert state.daily_pnl == 150.0

    def test_open_position_count(self):
        """Count of open positions."""
        state = PortfolioState()
        assert state.open_position_count == 0
        state.open_positions = {1: {}, 2: {}, 3: {}}
        assert state.open_position_count == 3

    def test_total_basket_risk(self):
        """Total basket risk calculation."""
        state = PortfolioState()
        
        # Mock position
        class MockPos:
            lots = 1.0
            entry = 1.08542
            hard_stop = 1.08400
            _pip_value = 10.0
        
        state.open_positions[1] = MockPos()
        risk = state.total_basket_risk
        # (1.08542 - 1.08400) * 1.0 * 10.0 = 1.42
        assert risk > 0

    def test_frozen_snapshot(self):
        """Frozen snapshot creation."""
        state = PortfolioState()
        state.daily_pnl  # Access to trigger property computation
        
        snapshot = state.get_frozen_snapshot()
        
        assert isinstance(snapshot, FrozenPortfolioSnapshot)
        assert snapshot.net_equity == 10_000.0
        assert snapshot.daily_pnl == 0.0
        assert snapshot.open_position_count == 0


class TestFrozenPortfolioSnapshot:
    """Test FrozenPortfolioSnapshot immutability."""

    def test_snapshot_immutable(self):
        """Frozen dataclass is immutable."""
        snapshot = FrozenPortfolioSnapshot(
            net_equity=10_000.0,
            starting_equity=10_000.0,
            daily_pnl=0.0,
            open_position_count=0,
            total_basket_risk=0.0,
            margin_utilisation=0.0,
            day_locked=False,
            circuit_breaker=False,
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            snapshot.net_equity = 9_999.0

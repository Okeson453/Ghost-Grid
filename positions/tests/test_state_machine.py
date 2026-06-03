"""
tests/positions/test_state_machine.py
Unit tests for positions/state_machine.py
"""

import pytest
from unittest.mock import Mock
from positions.state_machine import PositionStateMachine
from positions.models import PositionState, ExitReason


class MockMarketSnapshot:
    """Mock MarketSnapshot for testing."""

    def __init__(self):
        self.mid = 1.0900
        self.atr_1m = 0.0050
        self.m1 = []
        self.m5 = []
        self.cvd = {}


class TestPositionStateMachine:
    """Test suite for PositionStateMachine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sm = PositionStateMachine(
            position_id=1,
            symbol="EURUSD",
            direction="LONG",
            entry=1.0900,
            stop_loss=1.0850,
            lots=1.0,
            fill_ts_ms=1000000,
            pip_value=10.0,
            pip_size=0.0001,
        )

    def test_initial_state(self):
        """Test initial state is OPEN_UNREALIZED."""
        assert self.sm.state == PositionState.OPEN_UNREALIZED
        assert self.sm.position_id == 1
        assert self.sm.symbol == "EURUSD"

    def test_calc_pnl_long_positive(self):
        """Test PnL calculation for LONG positive."""
        pnl = self.sm._calc_pnl(1.0950)
        assert pnl > 0

    def test_calc_pnl_long_negative(self):
        """Test PnL calculation for LONG negative."""
        pnl = self.sm._calc_pnl(1.0850)
        assert pnl < 0

    def test_hard_stop_hit_long(self):
        """Test hard stop detection for LONG."""
        snap = MockMarketSnapshot()
        snap.mid = 1.0849
        exit_reason = self.sm.on_tick(snap.mid, snap)
        assert exit_reason == ExitReason.HARD_STOP

    def test_hard_stop_not_hit_long(self):
        """Test hard stop is not hit when price above it."""
        snap = MockMarketSnapshot()
        snap.mid = 1.0900
        exit_reason = self.sm.on_tick(snap.mid, snap)
        assert exit_reason is None

    def test_max_profit_tracking(self):
        """Test that max profit is tracked."""
        snap = MockMarketSnapshot()
        snap.mid = 1.0950
        self.sm.on_tick(snap.mid, snap)
        assert self.sm.max_profit > 0

    def test_force_close(self):
        """Test force close."""
        snap = MockMarketSnapshot()
        snap.mid = 1.0920
        exit_reason = self.sm.force_close(ExitReason.NUCLEAR, snap.mid)
        assert exit_reason == ExitReason.NUCLEAR
        assert self.sm.state == PositionState.CLOSED_NUCLEAR

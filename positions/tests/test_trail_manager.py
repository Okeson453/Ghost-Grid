"""
tests/positions/test_trail_manager.py
Unit tests for positions/trail_manager.py
"""

import pytest
from positions.trail_manager import TrailManager, compute_trail_distance


class TestTrailManager:
    """Test suite for TrailManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager_long = TrailManager(1, "LONG", "EURUSD")
        self.manager_short = TrailManager(2, "SHORT", "EURUSD")

    def test_trail_arm_long(self):
        """Test arming trail stop for LONG position."""
        entry = 1.0900
        atr = 0.0050
        trail = self.manager_long.arm(entry, atr)
        assert trail < entry  # Trail should be below entry for LONG
        assert self.manager_long.is_armed

    def test_trail_arm_short(self):
        """Test arming trail stop for SHORT position."""
        entry = 1.0900
        atr = 0.0050
        trail = self.manager_short.arm(entry, atr)
        assert trail > entry  # Trail should be above entry for SHORT
        assert self.manager_short.is_armed

    def test_trail_not_armed_initially(self):
        """Test trail is not armed initially."""
        assert not self.manager_long.is_armed
        assert self.manager_long.trail_stop is None

    def test_trail_update_favorable_direction_long(self):
        """Test trail moves up for LONG."""
        entry = 1.0900
        atr = 0.0050
        self.manager_long.arm(entry, atr)
        initial_trail = self.manager_long.trail_stop

        # Price moves up
        new_price = 1.0950
        updated = self.manager_long.update(new_price, atr)
        assert updated is not None
        assert updated > initial_trail

    def test_trail_no_update_against_direction_long(self):
        """Test trail doesn't move down for LONG."""
        entry = 1.0900
        atr = 0.0050
        self.manager_long.arm(entry, atr)
        initial_trail = self.manager_long.trail_stop

        # Price moves down
        new_price = 1.0850
        updated = self.manager_long.update(new_price, atr)
        assert updated is None  # Trail should not move
        assert self.manager_long.trail_stop == initial_trail

    def test_trail_hit_long(self):
        """Test trail hit detection for LONG."""
        entry = 1.0900
        atr = 0.0050
        self.manager_long.arm(entry, atr)
        trail = self.manager_long.trail_stop

        # Price below trail
        assert self.manager_long.is_hit(trail - 0.0001)
        assert not self.manager_long.is_hit(trail + 0.0001)

    def test_trail_hit_short(self):
        """Test trail hit detection for SHORT."""
        entry = 1.0900
        atr = 0.0050
        self.manager_short.arm(entry, atr)
        trail = self.manager_short.trail_stop

        # Price above trail
        assert self.manager_short.is_hit(trail + 0.0001)
        assert not self.manager_short.is_hit(trail - 0.0001)


class TestComputeTrailDistance:
    """Test suite for compute_trail_distance function."""

    def test_trail_distance_basic(self):
        """Test basic trail distance calculation."""
        dist = compute_trail_distance("EURUSD", 0.0050)
        assert dist > 0
        assert isinstance(dist, float)

    def test_trail_distance_increases_with_atr(self):
        """Test that trail distance increases with ATR."""
        dist1 = compute_trail_distance("EURUSD", 0.0050)
        dist2 = compute_trail_distance("EURUSD", 0.0100)
        assert dist2 > dist1

    def test_trail_distance_floor(self):
        """Test that trail distance respects minimum floor."""
        # Very low ATR
        dist = compute_trail_distance("EURUSD", 0.0001)
        assert dist > 0  # Should be at least the floor

"""
tests/nuclear/test_cooldown.py
Unit tests for nuclear cooldown logic.
"""

import pytest
from nuclear.cooldown import apply_cooldown


class MockPortfolioState:
    """Mock PortfolioState for testing."""
    def __init__(self):
        self.realized_pnl = 100.0
        self.unrealized_pnl = 50.0
        self.starting_equity = 10000.0
        self.last_nuclear_ts = 0.0
        self.nuclear_count_today = 0
        self.day_locked = False
        self.circuit_breaker = False


def test_cooldown_inactive_at_start():
    """At start: cooldown not active."""
    state = MockPortfolioState()
    state.last_nuclear_ts = 0
    
    # Current time: 1 second after Unix epoch
    current_time_ms = 1000
    
    cooldown = apply_cooldown(state, current_time_ms)
    assert not cooldown.active
    assert state.circuit_breaker is False


def test_cooldown_active_shortly_after_nuclear():
    """Shortly after nuclear: cooldown active."""
    state = MockPortfolioState()
    current_time_ms = 10000
    state.last_nuclear_ts = current_time_ms  # Nuclear just fired
    state.nuclear_count_today = 1
    
    cooldown = apply_cooldown(state, current_time_ms + 1000)  # 1 second later
    assert cooldown.active
    assert state.circuit_breaker is True
    assert cooldown.remaining_s > 0


def test_cooldown_expires_after_15_minutes():
    """After 15 minutes: cooldown expires."""
    state = MockPortfolioState()
    current_time_ms = 10000
    state.last_nuclear_ts = current_time_ms
    
    # 15 minutes later
    later_time_ms = current_time_ms + (15 * 60 * 1000)
    cooldown = apply_cooldown(state, later_time_ms)
    
    assert not cooldown.active
    assert state.circuit_breaker is False
    assert cooldown.remaining_s == 0


def test_day_locked_after_two_nuclear():
    """≥2 nuclear events today → day_locked = True."""
    state = MockPortfolioState()
    state.nuclear_count_today = 2
    state.last_nuclear_ts = 10000
    
    current_time_ms = 11000
    cooldown = apply_cooldown(state, current_time_ms)
    
    assert cooldown.day_locked is True
    assert state.day_locked is True


def test_day_locked_false_with_one_nuclear():
    """Only 1 nuclear event → day_locked stays False."""
    state = MockPortfolioState()
    state.nuclear_count_today = 1
    
    cooldown = apply_cooldown(state, 10000)
    assert cooldown.day_locked is False

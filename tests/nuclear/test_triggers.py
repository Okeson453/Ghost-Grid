"""
tests/nuclear/test_triggers.py
Unit tests for nuclear trigger conditions.
"""

import pytest
from nuclear.triggers import evaluate_triggers


class MockPortfolioState:
    """Mock PortfolioState for testing."""
    def __init__(self):
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.starting_equity = 10000.0
        self.open_positions = {"pos1": True}  # Non-empty dict
        self.avg_basket_rsi = 50.0
        self.last_fill_latency_ms = 0.0
        self.avg_pair_correlation = 0.0


class TestNuclearTriggers:
    """Test all 7 nuclear trigger conditions."""

    def test_no_positions_returns_none(self):
        """No open positions → no nuclear."""
        state = MockPortfolioState()
        state.open_positions = {}
        result = evaluate_triggers(state)
        assert result is None

    def test_trigger_combined_profit(self):
        """Trigger: combined unrealised profit >= threshold."""
        state = MockPortfolioState()
        state.unrealized_pnl = 10.0

        result = evaluate_triggers(state)

        assert result == "COMBINED_PROFIT"

    def test_trigger_daily_gain_target(self):
        """Trigger: daily gain target >= 15% of starting equity."""
        state = MockPortfolioState()
        state.realized_pnl = 1500.0
        state.unrealized_pnl = 0.0

        result = evaluate_triggers(state)

        assert result == "DAILY_GAIN_TARGET"

    def test_trigger_loss_protection(self):
        """Trigger: floating loss <= -$6.00."""
        state = MockPortfolioState()
        state.unrealized_pnl = -6.0

        result = evaluate_triggers(state)

        assert result == "LOSS_PROTECTION"

    def test_trigger_daily_loss_limit(self):
        """Trigger: daily loss <= -4% of starting equity."""
        state = MockPortfolioState()
        state.realized_pnl = -400.0
        state.unrealized_pnl = 0.0

        result = evaluate_triggers(state)

        assert result == "DAILY_LOSS_LIMIT"

    def test_trigger_market_exhaustion_rsi_oversold(self):
        """Trigger: RSI < 25 (oversold) indicates exhaustion."""
        state = MockPortfolioState()
        state.avg_basket_rsi = 20.0  # Below 25
        result = evaluate_triggers(state)
        assert "MARKET_EXHAUSTION" in str(result)

    def test_trigger_market_exhaustion_rsi_overbought(self):
        """Trigger: RSI > 75 (overbought) indicates exhaustion."""
        state = MockPortfolioState()
        state.avg_basket_rsi = 80.0  # Above 75
        result = evaluate_triggers(state)
        assert "MARKET_EXHAUSTION" in str(result)

    def test_no_trigger_normal_conditions(self):
        """No trigger: normal trading conditions."""
        state = MockPortfolioState()
        state.unrealized_pnl = 5.0  # Profit but below combined profit threshold
        state.realized_pnl = 50.0
        state.avg_basket_rsi = 50.0  # Normal
        state.last_fill_latency_ms = 10.0  # Normal
        state.avg_pair_correlation = 0.3  # Normal

        result = evaluate_triggers(state)

        assert result is None

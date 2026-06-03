"""
tests/portfolio/test_mode_automaton.py
Unit tests for portfolio/mode_automaton.py
"""

import pytest
from portfolio.state import PortfolioState
from portfolio.mode_automaton import ModeAutomaton, ModeDecision, select_mode


class TestSelectMode:
    """Test suite for select_mode function."""

    def test_mode_normal_all_clear(self):
        """Test SCALP_NORMAL when all conditions are clear."""
        state = PortfolioState(nuclear_count_today=0)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=False,
            win_rate_last_20=0.60,
            current_drawdown_pct=0.05,
            current_regime="UPTREND",
        )
        assert decision.mode == "SCALP_NORMAL"
        assert "clear" in decision.reason.lower()

    def test_mode_reduced_yesterday_halt(self):
        """Test SCALP_REDUCED when yesterday ended in halt."""
        state = PortfolioState(nuclear_count_today=0)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=True,
            win_rate_last_20=0.60,
            current_drawdown_pct=0.05,
            current_regime="UPTREND",
        )
        assert decision.mode == "SCALP_REDUCED"
        assert "halt" in decision.reason.lower()

    def test_mode_reduced_nuclear_exits(self):
        """Test SCALP_REDUCED when ≥2 nuclear exits today."""
        state = PortfolioState(nuclear_count_today=2)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=False,
            win_rate_last_20=0.60,
            current_drawdown_pct=0.05,
            current_regime="UPTREND",
        )
        assert decision.mode == "SCALP_REDUCED"
        assert "nuclear" in decision.reason.lower()

    def test_mode_reduced_drawdown(self):
        """Test SCALP_REDUCED when drawdown > 12%."""
        state = PortfolioState(nuclear_count_today=0)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=False,
            win_rate_last_20=0.60,
            current_drawdown_pct=0.15,
            current_regime="UPTREND",
        )
        assert decision.mode == "SCALP_REDUCED"
        assert "drawdown" in decision.reason.lower()

    def test_mode_reduced_chop_low_winrate(self):
        """Test SCALP_REDUCED when CHOP regime with <45% win rate."""
        state = PortfolioState(nuclear_count_today=0)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=False,
            win_rate_last_20=0.40,
            current_drawdown_pct=0.05,
            current_regime="CHOP",
        )
        assert decision.mode == "SCALP_REDUCED"
        assert "win rate" in decision.reason.lower()

    def test_mode_normal_chop_high_winrate(self):
        """Test SCALP_NORMAL in CHOP with high win rate."""
        state = PortfolioState(nuclear_count_today=0)
        decision = select_mode(
            state=state,
            yesterday_loss_halt=False,
            win_rate_last_20=0.60,
            current_drawdown_pct=0.05,
            current_regime="CHOP",
        )
        assert decision.mode == "SCALP_NORMAL"


class TestModeAutomaton:
    """Test suite for ModeAutomaton class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.automaton = ModeAutomaton()
        self.state = PortfolioState(current_mode="SCALP_NORMAL")

    def test_apply_mode_decision_no_change(self):
        """Test applying same mode as current."""
        decision = ModeDecision("SCALP_NORMAL", "Test")
        changed = self.automaton.apply_mode_decision(self.state, decision)
        assert changed is False
        assert self.state.current_mode == "SCALP_NORMAL"

    def test_apply_mode_decision_change(self):
        """Test applying different mode."""
        decision = ModeDecision("SCALP_REDUCED", "Test reason")
        changed = self.automaton.apply_mode_decision(self.state, decision)
        assert changed is True
        assert self.state.current_mode == "SCALP_REDUCED"

    def test_is_normal_mode(self):
        """Test normal mode check."""
        self.state.current_mode = "SCALP_NORMAL"
        assert self.automaton.is_normal_mode(self.state) is True
        assert self.automaton.is_reduced_mode(self.state) is False

    def test_is_reduced_mode(self):
        """Test reduced mode check."""
        self.state.current_mode = "SCALP_REDUCED"
        assert self.automaton.is_reduced_mode(self.state) is True
        assert self.automaton.is_normal_mode(self.state) is False

    def test_mode_multiplier_normal(self):
        """Test risk multiplier for NORMAL mode."""
        self.state.current_mode = "SCALP_NORMAL"
        assert self.automaton.get_mode_multiplier(self.state) == 1.0

    def test_mode_multiplier_reduced(self):
        """Test risk multiplier for REDUCED mode."""
        self.state.current_mode = "SCALP_REDUCED"
        assert self.automaton.get_mode_multiplier(self.state) == 0.5

    def test_max_leverage_normal(self):
        """Test max leverage for NORMAL mode."""
        self.state.current_mode = "SCALP_NORMAL"
        assert self.automaton.get_max_leverage(self.state) == 30

    def test_max_leverage_reduced(self):
        """Test max leverage for REDUCED mode."""
        self.state.current_mode = "SCALP_REDUCED"
        assert self.automaton.get_max_leverage(self.state) == 15

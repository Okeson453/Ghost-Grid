"""
portfolio/mode_automaton.py
Trading mode automaton — two-state selector.

States:
  SCALP_NORMAL:  1% risk, 30× max leverage, full instrument universe
  SCALP_REDUCED: 0.5% risk, 15× max leverage, Tier 1 instruments only

Defensive conditions → SCALP_REDUCED:
  1. Yesterday ended in daily loss halt
  2. ≥2 nuclear exits today
  3. Current drawdown > 12% from equity peak
  4. Win rate of last 20 trades < 45% AND regime is CHOP
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from portfolio.state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModeDecision:
    mode: str  # "SCALP_NORMAL" | "SCALP_REDUCED"
    reason: str  # Human-readable reason for Telegram report


def select_mode(
    state: PortfolioState,
    yesterday_loss_halt: bool,
    win_rate_last_20: float,
    current_drawdown_pct: float,
    current_regime: str,
) -> ModeDecision:
    """
    Evaluate defensive conditions and select trading mode.
    Conservative bias: any single defensive condition triggers REDUCED.

    Args:
        state: Current PortfolioState
        yesterday_loss_halt: True if yesterday's session ended in daily loss halt
        win_rate_last_20: Win rate of last 20 trades (0.0-1.0)
        current_drawdown_pct: Current drawdown from peak (0.0-1.0)
        current_regime: Current regime ("UPTREND", "DOWNTREND", "CHOP", "CONSOLIDATION")

    Returns:
        ModeDecision with selected mode and reason
    """

    if yesterday_loss_halt:
        return ModeDecision(
            "SCALP_REDUCED", "Yesterday ended in daily loss halt"
        )

    if state.nuclear_count_today >= 2:
        return ModeDecision(
            "SCALP_REDUCED", f"≥2 nuclear exits today ({state.nuclear_count_today})"
        )

    if current_drawdown_pct > 0.12:
        return ModeDecision(
            "SCALP_REDUCED", f"Drawdown {current_drawdown_pct * 100:.1f}% > 12% threshold"
        )

    if current_regime == "CHOP" and win_rate_last_20 < 0.45:
        return ModeDecision(
            "SCALP_REDUCED",
            f"Win rate {win_rate_last_20 * 100:.0f}% < 45% in CHOP regime",
        )

    return ModeDecision("SCALP_NORMAL", "All defensive conditions clear")


class ModeAutomaton:
    """
    Manages trading mode transitions.
    Stateless — all state lives in PortfolioState.
    """

    def apply_mode_decision(self, state: PortfolioState, decision: ModeDecision) -> bool:
        """
        Apply mode decision to state if different from current mode.

        Returns:
            True if mode changed, False if mode unchanged
        """
        old_mode = state.current_mode
        state.current_mode = decision.mode

        if old_mode != decision.mode:
            logger.info(f"Mode transition: {old_mode} → {decision.mode} | {decision.reason}")
            return True
        return False

    def is_normal_mode(self, state: PortfolioState) -> bool:
        """Check if currently in SCALP_NORMAL mode."""
        return state.current_mode == "SCALP_NORMAL"

    def is_reduced_mode(self, state: PortfolioState) -> bool:
        """Check if currently in SCALP_REDUCED mode."""
        return state.current_mode == "SCALP_REDUCED"

    def get_mode_multiplier(self, state: PortfolioState) -> float:
        """
        Get the risk multiplier based on current mode.
        Used by risk/sizer.py to adjust lot sizes.

        SCALP_NORMAL:  1.0x (baseline)
        SCALP_REDUCED: 0.5x (half baseline risk)
        """
        if state.current_mode == "SCALP_REDUCED":
            return 0.5
        return 1.0

    def get_max_leverage(self, state: PortfolioState) -> int:
        """
        Get maximum leverage multiplier for current mode.

        SCALP_NORMAL:  30x
        SCALP_REDUCED: 15x
        """
        if state.current_mode == "SCALP_REDUCED":
            return 15
        return 30

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
    """Trading mode decision with reason."""

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
        yesterday_loss_halt: True if yesterday ended in loss halt
        win_rate_last_20: Win rate of last 20 trades (0.0-1.0)
        current_drawdown_pct: Drawdown from peak (0.0-1.0)
        current_regime: Current regime ("TREND", "CHOP", etc.)

    Returns:
        ModeDecision with selected mode and reason
    """
    # Condition 1: Yesterday ended in loss halt
    if yesterday_loss_halt:
        return ModeDecision("SCALP_REDUCED", "Yesterday ended in daily loss halt")

    # Condition 2: ≥2 nuclear exits today
    if state.nuclear_count_today >= 2:
        return ModeDecision(
            "SCALP_REDUCED", f"≥2 nuclear exits today ({state.nuclear_count_today})"
        )

    # Condition 3: Current drawdown > 12%
    if current_drawdown_pct > 0.12:
        return ModeDecision(
            "SCALP_REDUCED",
            f"Drawdown {current_drawdown_pct * 100:.1f}% > 12% threshold",
        )

    # Condition 4: Low win rate in CHOP
    if current_regime == "CHOP" and win_rate_last_20 < 0.45:
        return ModeDecision(
            "SCALP_REDUCED", f"Win rate {win_rate_last_20 * 100:.0f}% < 45% in CHOP"
        )

    return ModeDecision("SCALP_NORMAL", "All defensive conditions clear")

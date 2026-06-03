"""
portfolio/ledger.py
PnL ledger — aggregates across all open positions.

Called by: positions/registry.py on tick update and on close.
Updates: PortfolioState.unrealized_pnl, realized_pnl.
"""

from __future__ import annotations
import logging
from typing import Dict, Optional
from portfolio.state import PortfolioState

logger = logging.getLogger(__name__)


class Ledger:
    """
    Computes and applies portfolio-level PnL aggregates.
    Stateless — operates purely on PortfolioState.
    """

    def update_unrealized(
        self,
        state: PortfolioState,
        current_prices: Dict[str, float],  # symbol → current mid price
    ) -> None:
        """
        Recompute total unrealised PnL from all open positions.
        Called every 500ms by NuclearController.
        """
        total = 0.0
        for position_id, sm in state.open_positions.items():
            try:
                if not hasattr(sm, "symbol") or not hasattr(sm, "_calc_pnl"):
                    continue
                price = current_prices.get(sm.symbol)
                if price is None:
                    continue
                pnl = sm._calc_pnl(price)
                total += pnl
            except Exception as e:
                logger.warning(f"Error calculating PnL for position {position_id}: {e}")

        state.unrealized_pnl = total

    def record_close(
        self,
        state: PortfolioState,
        realized_pnl: float,
    ) -> None:
        """Add realised PnL from a closed position to the daily total."""
        state.realized_pnl += realized_pnl
        logger.debug(
            f"Ledger close: +{realized_pnl:.2f} | "
            f"daily_realized={state.realized_pnl:.2f}"
        )

    def reset_daily(self, state: PortfolioState, current_equity: float) -> None:
        """
        Reset daily PnL tracking at UTC midnight.
        WHY: daily_pnl resets; starting_equity updates to current equity.
        """
        state.starting_equity = current_equity
        state.realized_pnl = 0.0
        state.unrealized_pnl = 0.0
        state.day_locked = False
        state.nuclear_count_today = 0
        logger.info(f"Daily reset: new starting equity = {current_equity:.2f}")

    def get_daily_metrics(self, state: PortfolioState) -> Dict[str, float]:
        """
        Compute daily performance metrics.
        Returns: dict with keys: daily_pnl, daily_pnl_pct, realized_pnl, unrealized_pnl
        """
        daily_pnl = state.daily_pnl
        starting_equity = state.starting_equity

        if starting_equity <= 0:
            daily_pnl_pct = 0.0
        else:
            daily_pnl_pct = daily_pnl / starting_equity

        return {
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "realized_pnl": state.realized_pnl,
            "unrealized_pnl": state.unrealized_pnl,
            "net_equity": state.net_equity,
            "starting_equity": starting_equity,
        }

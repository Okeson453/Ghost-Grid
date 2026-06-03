"""
positions/registry.py
Active position registry — maintains all open PositionStateMachines.

Single source of truth for open positions.
Updates portfolio state on every tick.
Fires exit commands when state machine returns ExitReason.
"""

from __future__ import annotations
import logging
from typing import Dict, Optional, List, Tuple
from data.schema import MarketSnapshot
from positions.models import PositionState, ExitReason
from positions.state_machine import PositionStateMachine
from portfolio.state import PortfolioState
from portfolio.ledger import Ledger

logger = logging.getLogger(__name__)


class PositionRegistry:
    """
    Manages all open positions and coordinates with portfolio state.
    """

    def __init__(self) -> None:
        # position_id → PositionStateMachine
        self._positions: Dict[int, PositionStateMachine] = {}
        self._ledger = Ledger()

    def add_position(
        self, state_machine: PositionStateMachine, portfolio_state: PortfolioState
    ) -> None:
        """
        Register a new open position.

        Args:
            state_machine: Initialized PositionStateMachine
            portfolio_state: Portfolio state to update
        """
        position_id = state_machine.position_id
        self._positions[position_id] = state_machine
        portfolio_state.add_position(position_id, state_machine)
        logger.info(
            f"Position registered: {state_machine.symbol} {state_machine.direction} "
            f"id={position_id} entry={state_machine.entry:.5f} "
            f"sl={state_machine.hard_stop:.5f}"
        )

    def get_position(self, position_id: int) -> Optional[PositionStateMachine]:
        """Get a position by ID."""
        return self._positions.get(position_id)

    def get_all_open(self) -> List[PositionStateMachine]:
        """Get all open positions."""
        return list(self._positions.values())

    def process_tick(
        self, snap: MarketSnapshot, portfolio_state: PortfolioState
    ) -> List[Tuple[int, ExitReason]]:
        """
        Process a tick for all open positions.
        Returns list of (position_id, exit_reason) for positions to close.

        Args:
            snap: Current market snapshot
            portfolio_state: Portfolio state to update

        Returns:
            List of positions that should be closed
        """
        exits: List[Tuple[int, ExitReason]] = []

        for position_id, state_machine in list(self._positions.items()):
            try:
                exit_reason = state_machine.on_tick(snap.mid, snap)
                if exit_reason:
                    exits.append((position_id, exit_reason))
            except Exception as e:
                logger.error(
                    f"Error processing tick for position {position_id}: {e}",
                    exc_info=True,
                )

        # Update portfolio PnL
        current_prices = {snap.symbol: snap.mid}
        self._ledger.update_unrealized(portfolio_state, current_prices)

        return exits

    def remove_position(
        self, position_id: int, realized_pnl: float, portfolio_state: PortfolioState
    ) -> None:
        """
        Remove a closed position from the registry.

        Args:
            position_id: Position ID to remove
            realized_pnl: Final realized P&L for this position
            portfolio_state: Portfolio state to update
        """
        if position_id in self._positions:
            sm = self._positions.pop(position_id)
            portfolio_state.remove_position(position_id)
            self._ledger.record_close(portfolio_state, realized_pnl)
            logger.info(
                f"Position closed: {sm.symbol} id={position_id} "
                f"pnl={realized_pnl:.2f}"
            )

    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self._positions)

    def get_total_risk(self) -> float:
        """Calculate total portfolio risk in USD."""
        total = 0.0
        for sm in self._positions.values():
            try:
                risk = sm.lots * abs(sm.entry - sm.hard_stop) / sm._pip_size * sm._pip_value
                total += risk
            except Exception:
                pass
        return total

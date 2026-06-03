"""
portfolio/state.py
PortfolioState — live mutable state of the entire portfolio.

WHY mutable (not frozen):
State changes on every tick (unrealised PnL changes).
Immutable copy-on-write at this update frequency would create
excessive GC pressure. Single-threaded asyncio access — no locking needed.

Watchdog thread reads via get_frozen_snapshot() which returns a frozen copy.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class PortfolioState:
    """
    Mutable live portfolio state.
    Updated by: positions/registry.py, portfolio/ledger.py.
    Read by: risk/governor.py, nuclear/controller.py, watchdog/thread.py.
    """
    # Identity
    starting_equity: float = 10_000.0  # Equity at UTC midnight
    net_equity: float = 10_000.0  # Current equity (updated from MT5)

    # Daily PnL
    realized_pnl: float = 0.0  # Closed trades since midnight
    unrealized_pnl: float = 0.0  # Sum of all open position PnL

    @property
    def daily_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    # Open positions
    open_positions: Dict[int, Any] = field(default_factory=dict)

    @property
    def open_position_count(self) -> int:
        return len(self.open_positions)

    @property
    def total_basket_risk(self) -> float:
        """Sum of risk capital in all open positions."""
        total = 0.0
        for p in self.open_positions.values():
            if hasattr(p, 'lots') and hasattr(p, 'entry') and hasattr(p, 'hard_stop') and \
               hasattr(p, '_pip_size') and hasattr(p, '_pip_value'):
                risk = p.lots * abs(p.entry - p.hard_stop) / p._pip_size * p._pip_value
                total += risk
        return total

    # Execution state
    margin_utilisation: float = 0.0  # Fraction of available margin used
    last_fill_latency_ms: float = 0.0

    # Circuit breakers
    circuit_breaker: bool = False  # True = no new signals processed
    day_locked: bool = False  # True = no new trades until midnight

    # Nuclear tracking
    nuclear_count_today: int = 0
    last_nuclear_ts: float = 0.0

    # Regime / mode
    current_mode: str = "SCALP_NORMAL"

    # Correlation matrix (updated every 60s by portfolio/correlation.py)
    avg_pair_correlation: float = 0.0

    # Basket RSI (average RSI of all open position directions)
    avg_basket_rsi: float = 50.0

    def add_position(self, position_id: int, position_state: Any) -> None:
        """Add a position to the open positions registry."""
        self.open_positions[position_id] = position_state

    def remove_position(self, position_id: int) -> Optional[Any]:
        """Remove a position from the open positions registry."""
        return self.open_positions.pop(position_id, None)

    def get_frozen_snapshot(self) -> "FrozenPortfolioSnapshot":
        """
        Returns a frozen snapshot safe for reading from the watchdog OS thread.
        WHY: OS thread cannot safely read mutable asyncio state.
        """
        return FrozenPortfolioSnapshot(
            net_equity=self.net_equity,
            starting_equity=self.starting_equity,
            daily_pnl=self.daily_pnl,
            open_position_count=self.open_position_count,
            total_basket_risk=self.total_basket_risk,
            margin_utilisation=self.margin_utilisation,
            day_locked=self.day_locked,
            circuit_breaker=self.circuit_breaker,
        )


@dataclass(frozen=True)
class FrozenPortfolioSnapshot:
    """Immutable snapshot for cross-thread reads."""
    net_equity: float
    starting_equity: float
    daily_pnl: float
    open_position_count: int
    total_basket_risk: float
    margin_utilisation: float
    day_locked: bool
    circuit_breaker: bool

    @property
    def daily_loss_pct(self) -> float:
        """Percentage loss from starting equity."""
        if self.starting_equity <= 0:
            return 0.0
        return (self.daily_pnl / self.starting_equity)

    @property
    def daily_gain_pct(self) -> float:
        """Percentage gain from starting equity."""
        return self.daily_loss_pct  # Same calc for both

    @property
    def equity_drawdown_pct(self) -> float:
        """Maximum drawdown from starting equity."""
        if self.daily_loss_pct < 0:
            return abs(self.daily_loss_pct)
        return 0.0

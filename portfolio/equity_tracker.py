"""
portfolio/equity_tracker.py
Live equity tracking from MT5 bridge.

Ingests account balance updates from FILL messages and maintains
a rolling equity history for peak/drawdown calculation.
"""

from __future__ import annotations
import time
import logging
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from portfolio.state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass
class EquityRecord:
    """Single equity snapshot."""

    timestamp: float  # Unix epoch seconds
    equity: float  # Account equity at this moment


class EquityTracker:
    """
    Tracks live equity from MT5 bridge and maintains statistics
    for drawdown calculation and peak equity monitoring.
    """

    def __init__(self, history_length: int = 1000):
        """
        Initialize equity tracker.

        Args:
            history_length: Maximum number of equity records to keep
        """
        self.history: List[EquityRecord] = []
        self.history_length = history_length
        self.peak_equity: float = 10_000.0
        self.peak_equity_ts: float = time.time()
        self.low_equity: float = 10_000.0
        self.low_equity_ts: float = time.time()

    def record_equity(self, equity: float, timestamp: Optional[float] = None) -> None:
        """
        Record a new equity value.

        Args:
            equity: Current account equity
            timestamp: Unix timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = time.time()

        record = EquityRecord(timestamp=timestamp, equity=equity)
        self.history.append(record)

        # Trim history if too long
        if len(self.history) > self.history_length:
            self.history.pop(0)

        # Update peak and low
        if equity > self.peak_equity:
            self.peak_equity = equity
            self.peak_equity_ts = timestamp
            logger.debug(f"New peak equity: {equity:.2f}")

        if equity < self.low_equity:
            self.low_equity = equity
            self.low_equity_ts = timestamp

    def update_state_equity(self, state: PortfolioState) -> None:
        """Update PortfolioState with current equity."""
        if self.history:
            state.net_equity = self.history[-1].equity

    def get_peak_equity(self) -> float:
        """Get peak equity recorded."""
        return self.peak_equity

    def get_drawdown_pct(self) -> float:
        """
        Calculate current drawdown from peak equity.

        Returns:
            Drawdown as percentage (0.0-1.0)
        """
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.low_equity) / self.peak_equity)

    def get_drawdown_abs(self) -> float:
        """Get absolute drawdown amount from peak."""
        return self.peak_equity - self.low_equity

    def get_latest_equity(self) -> Optional[float]:
        """Get most recent equity value."""
        if self.history:
            return self.history[-1].equity
        return None

    def get_equity_history(self, seconds: int = 300) -> List[Tuple[float, float]]:
        """
        Get equity history for a time window.

        Args:
            seconds: Look back this many seconds

        Returns:
            List of (timestamp, equity) tuples
        """
        if not self.history:
            return []

        cutoff_time = time.time() - seconds
        return [
            (r.timestamp, r.equity) for r in self.history if r.timestamp >= cutoff_time
        ]

    def get_volatility(self, lookback_seconds: int = 300) -> float:
        """
        Calculate equity volatility over a time window.

        Returns:
            Standard deviation of equity changes
        """
        history = self.get_equity_history(lookback_seconds)
        if len(history) < 2:
            return 0.0

        equities = [eq for _, eq in history]
        changes = [equities[i + 1] - equities[i] for i in range(len(equities) - 1)]

        if not changes:
            return 0.0

        mean_change = sum(changes) / len(changes)
        variance = sum((c - mean_change) ** 2 for c in changes) / len(changes)
        return variance**0.5

    def reset_tracking(self) -> None:
        """Reset tracking for new session."""
        self.history.clear()
        self.peak_equity = self.low_equity
        self.peak_equity_ts = time.time()
        self.low_equity_ts = time.time()

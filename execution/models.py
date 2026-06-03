"""
execution/models.py
Domain objects for execution: orders, fills, responses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum


class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING = "PENDING"
    SENT = "SENT"
    FILL = "FILL"
    REJECT = "REJECT"
    FAILED = "FAILED"


class ExitReason(Enum):
    """Exit reasons for CLOSE commands."""
    PROFIT_TARGET = "PROFIT_TARGET"
    STOP_LOSS = "STOP_LOSS"
    CVD_DIVERGENCE = "CVD_DIVERGENCE"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    FORCED_CLOSE = "FORCED_CLOSE"


@dataclass(frozen=True)
class ValidatedOrder:
    """
    Order that passed all 8 risk checks and is approved for execution.
    WHY frozen: immutable once created, prevents accidental modification.
    """
    symbol: str
    direction: Literal["LONG", "SHORT"]
    lot_size: float
    entry_price: float
    h_c_score: int  # 0–180
    regime: str  # TREND|CHOP|BREAKOUT|REVERSAL
    session: str  # ASIA|LONDON|OVERLAP|NY
    confluence_count: int  # Number of confluences at entry
    timestamp_ms: int
    request_id: str  # Unique request identifier for deduplication


@dataclass(frozen=True)
class ExecutionCommand:
    """
    Command to be written to named pipe (ORDER or CLOSE).
    """
    command_type: Literal["ORDER", "CLOSE"]
    symbol: str
    direction: Optional[Literal["LONG", "SHORT"]]  # None for CLOSE
    lot_size: Optional[float]  # None for CLOSE
    entry_price: Optional[float]  # None for CLOSE
    position_id: Optional[int] = None  # For CLOSE commands
    exit_reason: Optional[str] = None  # For CLOSE commands
    metadata: str = ""  # Optional metadata string


@dataclass
class FillResult:
    """
    Response from MT5 after order execution.
    """
    status: OrderStatus
    symbol: str
    position_id: int
    fill_price: float
    fill_time_ms: int
    request_id: str
    reason: Optional[str] = None  # For REJECT/FAILED


@dataclass
class OrderRetry:
    """
    Tracks retry attempts for a single order.
    """
    request_id: str
    attempt: int = 1
    max_attempts: int = 2  # Single retry = 2 total attempts
    last_error: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING


@dataclass
class DispatchMetrics:
    """Metrics for named pipe dispatch operations."""
    orders_sent: int = 0
    closes_sent: int = 0
    dispatch_errors: int = 0
    pipe_timeouts: int = 0
    bytes_written: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.orders_sent = 0
        self.closes_sent = 0
        self.dispatch_errors = 0
        self.pipe_timeouts = 0
        self.bytes_written = 0


@dataclass
class FillHandlerMetrics:
    """Metrics for fill response parsing."""
    fills_received: int = 0
    rejects_received: int = 0
    failed_received: int = 0
    parse_errors: int = 0
    malformed_responses: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.fills_received = 0
        self.rejects_received = 0
        self.failed_received = 0
        self.parse_errors = 0
        self.malformed_responses = 0


@dataclass
class RetryMetrics:
    """Metrics for retry logic."""
    retries_attempted: int = 0
    retries_succeeded: int = 0
    retries_failed: int = 0
    abort_by_rejection: int = 0
    abort_by_error: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.retries_attempted = 0
        self.retries_succeeded = 0
        self.retries_failed = 0
        self.abort_by_rejection = 0
        self.abort_by_error = 0


@dataclass
class LeverageMetrics:
    """Metrics for dynamic leverage calculations."""
    leverage_calculations: int = 0
    leverage_1x_count: int = 0
    leverage_10x_count: int = 0
    leverage_20x_count: int = 0
    leverage_30x_count: int = 0
    calculation_errors: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.leverage_calculations = 0
        self.leverage_1x_count = 0
        self.leverage_10x_count = 0
        self.leverage_20x_count = 0
        self.leverage_30x_count = 0
        self.calculation_errors = 0


@dataclass
class CommanderMetrics:
    """Metrics for execution commander (high-level orchestration)."""
    positions_opened: int = 0
    positions_closed: int = 0
    execution_successes: int = 0
    execution_failures: int = 0
    total_commission_usd: float = 0.0
    total_pnl_usd: float = 0.0
    open_position_count: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.positions_opened = 0
        self.positions_closed = 0
        self.execution_successes = 0
        self.execution_failures = 0
        self.total_commission_usd = 0.0
        self.total_pnl_usd = 0.0
        self.open_position_count = 0

"""
execution/commander.py
High-level execution orchestrator.
WHY: Coordinates dispatch, fill handling, retry, and metrics across all execution components.
"""

from __future__ import annotations
import asyncio
from typing import Optional

from .models import (
    ValidatedOrder,
    ExecutionCommand,
    FillResult,
    OrderStatus,
    ExitReason,
    CommanderMetrics,
)
from .dispatcher import PipeDispatcher
from .fill_handler import FillHandler
from .retry import RetryOrchestrator
from .leverage import LeverageCalculator
from config import get_settings


class ExecutionCommander:
    """
    High-level orchestrator for position execution.
    WHY: Centralizes all execution logic, provides single public API.
    """

    def __init__(self, pipe_path: Optional[str] = None):
        settings = get_settings()
        self.pipe_path = pipe_path or settings.pipe_path

        self.dispatcher = PipeDispatcher(self.pipe_path)
        self.fill_handler = FillHandler()
        self.retry_orchestrator = RetryOrchestrator()
        self.leverage_calculator = LeverageCalculator()
        self._metrics = CommanderMetrics()

    async def open_position(
        self,
        order: ValidatedOrder,
        current_atr: float,
        current_price: float,
    ) -> Optional[FillResult]:
        """
        Execute order: dispatch → fill handling → retry on temp failure.

        Args:
            order: ValidatedOrder (passed all risk checks)
            current_atr: Current ATR for leverage calculation
            current_price: Current bid/mid for leverage calculation

        Returns: FillResult if successful, None if failed after retries
        """
        try:
            # Calculate dynamic leverage
            leverage_mult = self.leverage_calculator.calculate_leverage(
                current_atr, current_price
            )

            # Create ORDER command
            command = ExecutionCommand(
                command_type="ORDER",
                symbol=order.symbol,
                direction=order.direction,
                lot_size=leverage_mult,  # Base lot × leverage
                entry_price=current_price,
                metadata=f"H_c={order.h_c_score};regime={order.regime};confluence={order.confluence_count}",
            )

            # Dispatch with retry
            fill_result = await self._dispatch_with_retry(
                order.request_id,
                command,
            )

            if fill_result and fill_result.status == OrderStatus.FILL:
                self._metrics.positions_opened += 1
                self._metrics.execution_successes += 1
                self._metrics.open_position_count += 1
                self.retry_orchestrator.mark_success(order.request_id)
                return fill_result
            else:
                self._metrics.execution_failures += 1
                self.retry_orchestrator.mark_failed(order.request_id)
                return None

        except Exception as e:
            self._metrics.execution_failures += 1
            return None

    async def close_position(
        self,
        symbol: str,
        position_id: int,
        exit_reason: ExitReason,
    ) -> bool:
        """
        Close an open position.

        Args:
            symbol: Instrument symbol
            position_id: Position ID from fill
            exit_reason: Reason for exit (profit target, stop loss, etc.)

        Returns: True if close command sent successfully
        """
        try:
            # Create CLOSE command
            command = ExecutionCommand(
                command_type="CLOSE",
                symbol=symbol,
                direction=None,
                lot_size=None,
                entry_price=None,
                position_id=position_id,
                exit_reason=exit_reason.value,
            )

            # Dispatch (no retry on CLOSE for simplicity)
            success = await self.dispatcher.dispatch(command, timeout_s=5.0)

            if success:
                self._metrics.positions_closed += 1
                self._metrics.open_position_count = max(
                    0, self._metrics.open_position_count - 1
                )
            return success

        except Exception as e:
            return False

    async def _dispatch_with_retry(
        self,
        request_id: str,
        command: ExecutionCommand,
    ) -> Optional[FillResult]:
        """
        Dispatch a command with single retry on temporary failures.
        Returns: FillResult if successful, None if failed after retries.
        """
        attempt = 0
        max_attempts = 2

        while attempt < max_attempts:
            attempt += 1

            # Dispatch command
            success = await self.dispatcher.dispatch(command, timeout_s=5.0)

            if not success:
                error = "Dispatch failed"
                if self.retry_orchestrator.should_retry(request_id, None, error):
                    await asyncio.sleep(0.5)  # Brief backoff before retry
                    continue
                else:
                    return None

            # Dispatch succeeded, but we don't have fill confirmation yet
            # In production, this would read from pipe reader in main.py
            # For now, assume dispatch success = order accepted
            return FillResult(
                status=OrderStatus.FILL,
                symbol=command.symbol,
                position_id=0,  # Will be populated by MT5 response
                fill_price=command.entry_price or 0.0,
                fill_time_ms=0,
                request_id=request_id,
                reason=None,
            )

        return None

    @property
    def metrics(self) -> CommanderMetrics:
        """Expose metrics."""
        return self._metrics

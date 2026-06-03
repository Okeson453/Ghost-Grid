"""
execution/retry.py
Single retry logic with abort conditions.
WHY: Distinguishes temporary failures (retry) from permanent ones (abort).
"""

from __future__ import annotations
from typing import Optional

from .models import OrderRetry, OrderStatus, FillResult, RetryMetrics


class RetryOrchestrator:
    """
    Manage retry attempts with clear abort conditions.
    WHY: Prevents infinite retry loops on rejected orders.
    """

    def __init__(self):
        self._metrics = RetryMetrics()
        self._retries: dict[str, OrderRetry] = {}

    def should_retry(
        self,
        request_id: str,
        fill_result: Optional[FillResult],
        error: Optional[str] = None,
    ) -> bool:
        """
        Determine if an order should be retried.

        Retry conditions (temporary):
        - Timeout (pipe I/O error)
        - Buffer full (broker temporarily unavailable)

        Abort conditions (permanent):
        - REJECT (order validation failed)
        - FAILED (slippage, margin, etc.)
        - Already retried once (max 2 attempts total)

        Args:
            request_id: Unique order request ID
            fill_result: Response from dispatcher (if available)
            error: Error message from dispatcher

        Returns: True if should retry, False if abort
        """
        # Get or create retry tracker
        if request_id not in self._retries:
            self._retries[request_id] = OrderRetry(request_id=request_id)

        retry = self._retries[request_id]

        # Check if already retried once
        if retry.attempt >= retry.max_attempts:
            self._metrics.retries_failed += 1
            self._retries.pop(request_id, None)
            return False

        # Check abort conditions
        if fill_result:
            if fill_result.status == OrderStatus.REJECT:
                self._metrics.abort_by_rejection += 1
                self._retries.pop(request_id, None)
                return False

            if fill_result.status == OrderStatus.FAILED:
                self._metrics.abort_by_error += 1
                self._retries.pop(request_id, None)
                return False

        # Temporary failures (retry)
        if error:
            if "timeout" in error.lower() or "buffer" in error.lower():
                self._metrics.retries_attempted += 1
                retry.attempt += 1
                retry.last_error = error
                return True

        # Default: retry on generic errors
        self._metrics.retries_attempted += 1
        retry.attempt += 1
        retry.last_error = error
        return True

    def mark_success(self, request_id: str) -> None:
        """Mark a retry attempt as successful."""
        self._metrics.retries_succeeded += 1
        self._retries.pop(request_id, None)

    def mark_failed(self, request_id: str) -> None:
        """Mark a retry attempt as failed (abort)."""
        self._metrics.retries_failed += 1
        self._retries.pop(request_id, None)

    def get_retry_info(self, request_id: str) -> Optional[OrderRetry]:
        """Get retry state for a request."""
        return self._retries.get(request_id)

    @property
    def metrics(self) -> RetryMetrics:
        """Expose metrics."""
        return self._metrics

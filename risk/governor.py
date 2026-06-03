"""
risk/governor.py
RiskGovernor — public API for the risk layer.

Single entry point: governor.validate(order, portfolio) → ValidationResult
Wraps validator.py with logging and metrics hooks.
"""

from __future__ import annotations
import logging

from risk.validator import validate_order
from risk.models import ProposedOrder, PortfolioSnapshot, ValidationResult

logger = logging.getLogger(__name__)


class RiskGovernor:
    """
    Stateless risk validator.
    One instance shared across the entire system.
    Thread-safe: no mutable state.
    """

    def validate(
        self,
        order: ProposedOrder,
        portfolio: PortfolioSnapshot,
    ) -> ValidationResult:
        """
        Validate a proposed order against current portfolio state.
        Logs all rejections. Never raises — returns ValidationResult on error.
        """
        try:
            return validate_order(order, portfolio)
        except Exception as e:
            logger.error(f"RiskGovernor unexpected error: {e}", exc_info=True)
            return ValidationResult(
                approved=False,
                reason=f"INTERNAL_ERROR: {e}",
                lot_size=None,
            )

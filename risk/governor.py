"""
risk/governor.py
RiskGovernor — public API for the risk layer.

SOURCE: GHOST-GRID-MT5-Design.md § IV Risk Governor

Single entry point: governor.validate(order, portfolio) → ValidationResult

Wraps validator.py with logging and metrics hooks.
Implements 8-check validation chain (all must pass):
  1. Day locked check (fastest)
  2. Daily gain check (15% target)
  3. Daily loss check (4% limit → hard stop)
  4. Concurrent position cap (5 max)
  5. Basket risk check (5% total heat)
  6. Reward:Risk ratio (1.5x minimum)
  7. Spread validation (0.12% max)
  8. Margin utilization (80% max buffer)

All limits are IMMUTABLE at runtime (defined in risk/constants.py).
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

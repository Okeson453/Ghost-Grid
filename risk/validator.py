"""
risk/validator.py
8-check pre-trade validation chain.

All 8 checks must pass for an order to be approved.
Checks are ordered: fastest/cheapest first.
First failure short-circuits — remaining checks are not evaluated.

WHY short-circuit: if daily loss limit is already breached (check 3),
there is no point computing basket risk or margin (checks 2, 8).
"""

from __future__ import annotations
import logging

from risk.constants import (
    MAX_RISK_PER_TRADE,
    MAX_BASKET_RISK,
    MAX_DAILY_LOSS,
    MAX_DAILY_GAIN,
    MAX_CONCURRENT,
    MIN_RR_RATIO,
    MAX_SPREAD_PCT,
    MARGIN_BUFFER,
)
from risk.models import ProposedOrder, PortfolioSnapshot, ValidationResult
from risk.sizer import calculate_lot_size

logger = logging.getLogger(__name__)


def validate_order(
    order: ProposedOrder,
    portfolio: PortfolioSnapshot,
) -> ValidationResult:
    """
    Run all 8 risk checks against the proposed order and portfolio state.

    Returns ValidationResult(approved=True, lot_size=N) on full pass.
    Returns ValidationResult(approved=False, reason=...) on first failure.
    """

    equity = portfolio.net_equity
    trade_risk = equity * MAX_RISK_PER_TRADE

    checks: list[tuple[bool, str]] = [
        # 1. Day locked check (fastest — no arithmetic needed)
        (
            not portfolio.day_locked,
            "DAY_LOCKED: daily loss limit already triggered — no new trades until midnight",
        ),
        # 2. Daily gain check
        (
            portfolio.daily_pnl < equity * MAX_DAILY_GAIN,
            f"DAILY_GAIN: daily gain {portfolio.daily_pnl:.2f} exceeds "
            f"{MAX_DAILY_GAIN*100:.0f}% target — halting for the day",
        ),
        # 3. Daily loss check
        (
            portfolio.daily_pnl > -(equity * MAX_DAILY_LOSS),
            f"DAILY_LOSS: daily loss {portfolio.daily_pnl:.2f} exceeds "
            f"{MAX_DAILY_LOSS*100:.0f}% limit",
        ),
        # 4. Concurrent position cap
        (
            portfolio.open_position_count < MAX_CONCURRENT,
            f"CONCURRENT: {portfolio.open_position_count}/{MAX_CONCURRENT} "
            "positions open — at capacity",
        ),
        # 5. Basket risk check
        (
            portfolio.total_basket_risk + trade_risk <= equity * MAX_BASKET_RISK,
            f"BASKET_RISK: adding {trade_risk:.2f} would exceed "
            f"{MAX_BASKET_RISK*100:.0f}% portfolio heat",
        ),
        # 6. Reward:Risk ratio
        (
            order.rr_ratio >= MIN_RR_RATIO,
            f"RR_RATIO: {order.rr_ratio:.2f} below minimum {MIN_RR_RATIO}",
        ),
        # 7. Spread check
        (
            order.spread_pct < MAX_SPREAD_PCT,
            f"SPREAD: {order.spread_pct*100:.4f}% exceeds "
            f"{MAX_SPREAD_PCT*100:.4f}% maximum",
        ),
        # 8. Margin utilisation
        (
            portfolio.margin_utilisation < MARGIN_BUFFER,
            f"MARGIN: utilisation {portfolio.margin_utilisation*100:.1f}% "
            f"exceeds {MARGIN_BUFFER*100:.0f}% buffer",
        ),
    ]

    for condition, reason in checks:
        if not condition:
            logger.info(f"Order rejected: {reason}")
            return ValidationResult(approved=False, reason=reason, lot_size=None)

    # All checks passed — compute lot size
    lot_size = calculate_lot_size(
        symbol=order.symbol,
        equity=equity,
        entry=order.entry_price,
        stop_loss=order.stop_loss,
    )

    logger.info(
        f"Order approved: {order.symbol} {order.direction} "
        f"{lot_size:.2f} lots @ {order.entry_price:.5f} SL={order.stop_loss:.5f}"
    )

    return ValidationResult(approved=True, reason=None, lot_size=lot_size)

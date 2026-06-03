"""
nuclear/cooldown.py
Nuclear cooldown — 15-minute lockout + daily halt after nuclear event.

After a nuclear exit:
  1. 15-minute cooldown: no new signals processed (circuit_breaker = True)
  2. Increment daily nuclear count
  3. If ≥2 nuclear events in one day: daily_locked = True (no new trades until midnight)

WHY 15 minutes:
After a nuclear event, the market is in emotional mode (buyer/seller panic).
The scoring system may produce false signals for 15 minutes as volatility
normalises. Better to sit out and avoid revenge trading.

WHY daily halt at ≥2 nuclear events:
Two nuclear fires in one day indicates the trading system is not
compatible with current market conditions. Halt trading until the
next session and investigate.
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

COOLDOWN_DURATION_S = 15 * 60  # 15 minutes


@dataclass(frozen=True)
class NuclearCooldown:
    """State of the nuclear cooldown."""

    active: bool
    remaining_s: float
    daily_nuclear_count: int
    day_locked: bool


def apply_cooldown(state, current_time_ms: int) -> NuclearCooldown:
    """
    Check and apply nuclear cooldown logic.
    Called every 500ms by NuclearController.

    Args:
        state:            PortfolioState
        current_time_ms:  Current time in Unix milliseconds

    Returns:
        NuclearCooldown snapshot
    """
    current_time_s = current_time_ms / 1000.0

    # ── Check if cooldown is still active ──────────────────────────────
    cooldown_elapsed_s = current_time_s - (state.last_nuclear_ts / 1000.0)
    cooldown_active = cooldown_elapsed_s < COOLDOWN_DURATION_S

    remaining_s = max(0, COOLDOWN_DURATION_S - cooldown_elapsed_s)

    # ── Apply day halt if ≥2 nuclear events today ──────────────────────
    if state.nuclear_count_today >= 2:
        state.day_locked = True
        logger.warning(f"Day locked: {state.nuclear_count_today} nuclear events today")

    # ── Apply circuit breaker if cooldown active ──────────────────────
    if cooldown_active:
        state.circuit_breaker = True
    else:
        state.circuit_breaker = False

    return NuclearCooldown(
        active=cooldown_active,
        remaining_s=remaining_s,
        daily_nuclear_count=state.nuclear_count_today,
        day_locked=state.day_locked,
    )

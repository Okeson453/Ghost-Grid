"""
nuclear/controller.py
NuclearController — main 500ms asyncio task monitoring portfolio state.

SOURCE: GHOST-GRID-MT5-Design.md § VI Nuclear Portfolio Guardian

Runs every 500ms and:
  1. Polls PortfolioState for open positions
  2. Evaluates all 7 trigger conditions (in nuclear/triggers.py)
  3. If any trigger fires: execute_nuclear_close() and apply_cooldown()
  4. Logs and alerts via Telegram on nuclear event

7 Nuclear Triggers (any single one fires all-close):
  1. COMBINED_PROFIT: unrealised PnL ≥ $10.00
  2. DAILY_GAIN_TARGET: daily PnL ≥ 15% of equity
  3. LOSS_PROTECTION: unrealised PnL ≤ -$6.00
  4. DAILY_LOSS_LIMIT: daily PnL ≤ -4% of equity (permanent day halt)
  5. MARKET_EXHAUSTION: avg basket RSI < 25 or > 75
  6. LATENCY_ANOMALY: last fill latency > 500ms
  7. CORRELATION_SPIKE: avg pair correlation > 0.80

WHY 500ms poll interval:
Portfolio state changes frequently (tick updates, unrealised PnL changes).
500ms gives sub-second responsiveness for circuit breaker logic without
excessive CPU load from eval-per-tick.

WHY async task:
Nuclear must run independently of scoring pipeline.
If scoring is slow or blocked, nuclear still monitors and fires.
"""

from __future__ import annotations
import asyncio
import logging
import time

from nuclear.models import NuclearReason, NuclearEvent
from nuclear.triggers import evaluate_triggers
from nuclear.executor import execute_nuclear_close
from nuclear.cooldown import apply_cooldown

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.5  # 500ms


class NuclearController:
    """
    Portfolio-level circuit breaker.
    Runs as an independent asyncio task.
    """

    def __init__(self, state, commander, telegram_alerts=None):
        """
        Args:
            state:            PortfolioState (mutable, updated by other tasks)
            commander:        ExecutionCommander (for close() calls)
            telegram_alerts:  Optional telegram.alerts module for notifications
        """
        self.state = state
        self.commander = commander
        self.telegram = telegram_alerts

    async def run(self) -> None:
        """
        Main 500ms monitoring loop.
        Runs until task is cancelled.
        """
        logger.info("NuclearController started (500ms poll)")

        while True:
            try:
                await self._poll_and_check()
                await asyncio.sleep(POLL_INTERVAL_S)
            except asyncio.CancelledError:
                logger.info("NuclearController cancelled")
                raise
            except Exception as e:
                logger.error(f"NuclearController error: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_S)

    async def _poll_and_check(self) -> None:
        """
        Single iteration: evaluate triggers, fire nuclear if needed.
        """
        current_time_ms = int(time.time() * 1000)

        # ── Evaluate all triggers ──────────────────────────────────────
        reason_str = evaluate_triggers(self.state)

        if reason_str is None:
            # No trigger — apply cooldown and return
            apply_cooldown(self.state, current_time_ms)
            return

        # ── Nuclear fires! ─────────────────────────────────────────────
        logger.critical(f"NUCLEAR TRIGGERED: {reason_str}")

        # Execute close-all
        close_results = await execute_nuclear_close(
            self.state, self.commander, reason_str
        )

        # Record nuclear event
        positions_closed = len(close_results)
        event = NuclearEvent(
            reason=NuclearReason(reason_str),
            timestamp_ms=current_time_ms,
            positions_closed=positions_closed,
            portfolio_pnl=self.state.daily_pnl,
            equity_at_fire=self.state.net_equity,
        )

        # Update state
        self.state.last_nuclear_ts = current_time_ms
        self.state.nuclear_count_today += 1

        # Apply cooldown
        cooldown = apply_cooldown(self.state, current_time_ms)
        logger.info(
            f"Nuclear cooldown applied: {cooldown.remaining_s:.0f}s remaining"
        )

        # Send Telegram alert
        if self.telegram:
            try:
                await self.telegram.send_nuclear_alert(event, cooldown)
            except Exception as e:
                logger.error(f"Failed to send nuclear alert: {e}")

        logger.warning(
            f"Nuclear event recorded: {reason_str} | "
            f"Positions: {positions_closed} | "
            f"Daily PnL: {self.state.daily_pnl:.2f} | "
            f"Nuclear count today: {self.state.nuclear_count_today}"
        )

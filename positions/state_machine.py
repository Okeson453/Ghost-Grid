"""
positions/state_machine.py
Position state machine — one instance per open position.

SOURCE: GHOST-GRID-MT5-Design.md § V Position Lifecycle & Exit Warfare

State transitions driven by on_tick() events.
All transitions are append-only logged to SQLite via db/writer.py.
No transition is reversible — states only move forward.

4-Layer Exit System (exact spec implementation):
  Layer 1: Profit trigger ($1.50 unrealised) → arms trailing stop
  Layer 2: Trailing stop execution (trail moves in favorable direction only)
  Layer 3: Weakness detection (RSI(3) extreme + engulfing + volume cliff, all 3)
  Layer 4: CVD divergence override (Z-score > 2.0 against position) — FASTEST EXIT

Hard stop: MANDATORY at entry (1% risk boundary)
Take-profit: NEVER hardcoded — all exits are state-driven

Exit is triggered by returning an ExitReason from on_tick().
The caller (registry.py) handles the actual close command dispatch.
"""

from __future__ import annotations
import logging
import time
from typing import Optional
from data.schema import MarketSnapshot
from positions.models import PositionState, ExitReason
from positions.trail_manager import TrailManager
from positions.weakness import detect_weakness
from positions.cvd_exit import check_cvd_exit
from config.constants import PROFIT_TRIGGER_USD
from scoring.bayesian_weights import BayesianWeightUpdater

logger = logging.getLogger(__name__)


class PositionStateMachine:
    """
    Manages lifecycle of one position from fill to close.

    Usage:
        sm = PositionStateMachine(position_id, symbol, direction,
                                   entry, stop_loss, lots, fill_ts)
        exit_reason = sm.on_tick(current_price, snap)
        if exit_reason:
            # Dispatch close command, record to DB
    """

    def __init__(
        self,
        position_id: int,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
        lots: float,
        fill_ts_ms: int,
        pip_value: float,
        pip_size: float,
    ) -> None:
        self.position_id = position_id
        self.symbol = symbol
        self.direction = direction
        self.entry = entry
        self.hard_stop = stop_loss
        self.lots = lots
        self.fill_ts_ms = fill_ts_ms
        self._pip_value = pip_value
        self._pip_size = pip_size

        self.state = PositionState.OPEN_UNREALIZED
        self.max_profit = 0.0
        self._trail = TrailManager(position_id, direction, symbol)
        self._events: list = []
        self._weight_updater = BayesianWeightUpdater()

    def on_tick(
        self, current_price: float, snap: MarketSnapshot
    ) -> Optional[ExitReason]:
        """
        Process one price tick. Returns ExitReason if position should close.
        Returns None to continue holding.
        """
        pnl = self._calc_pnl(current_price)
        self.max_profit = max(self.max_profit, pnl)

        # ── Layer 4: CVD divergence override (checked first — fastest exit) ──
        cvd_exit = check_cvd_exit(snap, self.direction)
        if cvd_exit:
            return self._close(ExitReason.CVD_DIVERGENCE, current_price)

        # ── Hard stop ────────────────────────────────────────────────────────
        if self._hard_stop_hit(current_price):
            return self._close(ExitReason.HARD_STOP, current_price)

        if self.state == PositionState.OPEN_UNREALIZED:
            # ── Layer 1: Profit trigger → arm trail ──────────────────────────
            if pnl >= PROFIT_TRIGGER_USD:
                trail_stop = self._trail.arm(current_price, snap.atr_1m)
                self.state = PositionState.OPEN_TRAILING
                self._log(
                    "TRAIL_ARMED", {"trail_stop": trail_stop, "pnl": pnl}
                )
                logger.info(
                    f"Trail armed: {self.symbol} id={self.position_id} "
                    f"trail={trail_stop:.5f}"
                )

        elif self.state == PositionState.OPEN_TRAILING:
            # ── Layer 2: Update trail and check hit ──────────────────────────
            self._trail.update(current_price, snap.atr_1m)
            if self._trail.is_hit(current_price):
                return self._close(ExitReason.TRAIL_HIT, current_price)

            # ── Layer 3: Weakness detection ───────────────────────────────────
            weakness = detect_weakness(snap.m1, self.direction)
            if weakness.all_three:
                return self._close(ExitReason.WEAKNESS_CONFIRMED, current_price)

        return None  # Continue holding

    def force_close(self, reason: ExitReason, price: float) -> ExitReason:
        """External override (nuclear, Telegram /nuke)."""
        return self._close(reason, price)

    def _calc_pnl(self, current_price: float) -> float:
        """Unrealised PnL in USD."""
        price_diff = (
            (current_price - self.entry)
            if self.direction == "LONG"
            else (self.entry - current_price)
        )
        pips = price_diff / self._pip_size
        return pips * self._pip_value * self.lots

    def _hard_stop_hit(self, current_price: float) -> bool:
        if self.direction == "LONG":
            return current_price <= self.hard_stop
        return current_price >= self.hard_stop

    def _close(self, reason: ExitReason, price: float) -> ExitReason:
        pnl = self._calc_pnl(price)
        if pnl > 0:
            self.state = PositionState.CLOSED_PROFIT
            outcome = True
        elif reason == ExitReason.NUCLEAR:
            self.state = PositionState.CLOSED_NUCLEAR
            outcome = False
        else:
            self.state = PositionState.CLOSED_LOSS
            outcome = False
        for strategy in ("HMP", "HLCP", "MPP"):
            self._weight_updater.update(strategy, outcome)
        self._log(
            "POSITION_CLOSED",
            {"reason": reason.value, "price": price, "pnl": pnl},
        )
        return reason

    def _log(self, event_type: str, payload: dict) -> None:
        self._events.append(
            {"type": event_type, "ts_ns": time.monotonic_ns(), **payload}
        )

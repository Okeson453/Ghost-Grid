"""
positions/exit_engine.py
4-layer exit coordinator.

Ordered by priority (what triggers first):
  Layer 4: CVD divergence override (institutional breakdown)
  Layer 1: Hard stop (risk control)
  Layer 2: Profit trigger → arm trailing stop
  Layer 3: Trailing stop hit + weakness confirmation

Each layer is stateless relative to the others — state lives in
PositionStateMachine. ExitEngine just evaluates conditions.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from data.schema import MarketSnapshot
from positions.models import ExitReason
from positions.trail_manager import TrailManager
from positions.weakness import detect_weakness
from positions.cvd_exit import check_cvd_exit
from config.constants import PROFIT_TRIGGER_USD


@dataclass(frozen=True)
class ExitEvaluation:
    should_exit: bool
    reason: Optional[ExitReason]
    layer: Optional[int]  # 1, 2, 3, or 4


class ExitEngine:
    """
    Evaluates 4-layer exit logic for a single position.
    Stateless — all state lives in PositionStateMachine.
    """

    @staticmethod
    def evaluate(
        snap: MarketSnapshot,
        direction: str,
        entry_price: float,
        hard_stop: float,
        current_pnl: float,
        trail_manager: TrailManager,
        m1_bars: list,
    ) -> ExitEvaluation:
        """
        Evaluate all 4 exit layers in priority order.

        Returns ExitEvaluation with first trigger (if any).
        """
        # Layer 4: CVD divergence (highest priority)
        if check_cvd_exit(snap, direction):
            return ExitEvaluation(True, ExitReason.CVD_DIVERGENCE, 4)

        # Layer 1: Hard stop
        current_price = snap.mid
        if direction == "LONG" and current_price <= hard_stop:
            return ExitEvaluation(True, ExitReason.HARD_STOP, 1)
        if direction == "SHORT" and current_price >= hard_stop:
            return ExitEvaluation(True, ExitReason.HARD_STOP, 1)

        # Layer 2: Profit trigger → arm trailing stop
        if current_pnl >= PROFIT_TRIGGER_USD and not trail_manager.is_armed:
            return ExitEvaluation(False, None, 2)

        # Layer 3: Trailing stop + weakness
        if trail_manager.is_armed:
            if trail_manager.is_hit(current_price):
                return ExitEvaluation(True, ExitReason.TRAIL_HIT, 3)

            weakness = detect_weakness(m1_bars, direction)
            if weakness.all_three:
                return ExitEvaluation(True, ExitReason.WEAKNESS_CONFIRMED, 3)

        return ExitEvaluation(False, None, None)

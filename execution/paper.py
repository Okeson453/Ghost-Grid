"""
execution/paper.py
PaperExecutionCommander: lightweight paper trading execution engine.
"""
from __future__ import annotations
import random
import asyncio
from typing import Optional

from .models import FillResult, OrderStatus
from .models import CommanderMetrics


class PaperExecutionCommander:
    def __init__(self):
        self._next_id = 1000
        self._metrics = CommanderMetrics()
        self._positions: dict[int, dict] = {}

    async def open_position(self, order, current_atr, current_price) -> Optional[FillResult]:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        # Small rejection probability to simulate slippage/rejects
        if random.random() > 0.98:
            return None

        position_id = self._next_id
        self._next_id += 1
        self._positions[position_id] = {"symbol": order.symbol, "entry": current_price}

        return FillResult(
            status=OrderStatus.FILL,
            symbol=order.symbol,
            position_id=position_id,
            fill_price=current_price + random.uniform(-0.0001, 0.0001),
            fill_time_ms=int(asyncio.get_event_loop().time() * 1000),
            request_id=order.request_id,
        )

    async def close_position(self, symbol: str, position_id: int, exit_reason) -> bool:
        if position_id not in self._positions:
            return False
        del self._positions[position_id]
        return True

    @property
    def metrics(self) -> CommanderMetrics:
        return self._metrics

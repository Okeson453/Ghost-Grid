"""
risk/sizer.py
Lot size calculator — fixed fractional, always rounds DOWN.

Formula:
  risk_capital = equity × MAX_RISK_PER_TRADE       (e.g. $10,000 × 0.01 = $100)
  pip_risk     = |entry - stop_loss| / pip_size     (e.g. 0.00200 / 0.0001 = 20 pips)
  lot_size     = risk_capital / (pip_risk × pip_value_per_lot)

  Example:
    equity       = $10,000
    risk_capital = $100
    pip_risk     = 20 pips
    pip_value    = $10 per pip per lot (EURUSD standard)
    lot_size     = $100 / (20 × $10) = 0.50 lots

Always rounds DOWN to lot_step granularity.
Never returns less than MIN_LOT_SIZE or more than MAX_LOT_SIZE.
"""

from __future__ import annotations
import math

from config.instruments import get_instrument
from risk.constants import MAX_RISK_PER_TRADE, MIN_LOT_SIZE, MAX_LOT_SIZE


def calculate_lot_size(
    symbol: str,
    equity: float,
    entry: float,
    stop_loss: float,
) -> float:
    """
    Calculate lot size for a trade.

    Args:
        symbol:    Instrument symbol (must be in INSTRUMENTS registry)
        equity:    Current net account equity in USD
        entry:     Entry price
        stop_loss: Stop loss price

    Returns:
        Lot size, rounded DOWN to lot_step, within [MIN_LOT_SIZE, MAX_LOT_SIZE]
    """
    instr = get_instrument(symbol)

    risk_capital = equity * MAX_RISK_PER_TRADE
    pip_distance = abs(entry - stop_loss) / instr.pip_size

    if pip_distance == 0:
        return MIN_LOT_SIZE  # Degenerate case — return minimum

    raw_lots = risk_capital / (pip_distance * instr.pip_value)

    # Round DOWN to lot step (never round up — that would exceed 1% risk)
    floored = _floor_to_step(raw_lots, instr.lot_step)

    return max(MIN_LOT_SIZE, min(floored, MAX_LOT_SIZE))


def _floor_to_step(value: float, step: float) -> float:
    """
    Round value DOWN to nearest multiple of step.
    WHY math.floor not round: rounding up would exceed risk limit.
    """
    if step <= 0:
        return value
    return math.floor(value / step) * step


def compute_stop_loss(
    entry: float,
    direction: str,
    atr_5m: float,
    multiplier: float = 1.5,
) -> float:
    """
    Compute ATR-based stop loss.

    stop = entry - atr × multiplier  (LONG)
    stop = entry + atr × multiplier  (SHORT)

    WHY 1.5× ATR: wide enough to avoid normal volatility noise,
    tight enough to keep risk contained within 1%.
    """
    offset = atr_5m * multiplier
    if direction == "LONG":
        return entry - offset
    return entry + offset

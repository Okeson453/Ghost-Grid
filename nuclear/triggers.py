"""
nuclear/triggers.py
7 nuclear trigger conditions — pure functions, no side effects.

Each trigger: PortfolioState → bool
Evaluated in order by NuclearController.
First True triggers nuclear exit for the given reason.

WHY pure functions:
Triggers must be unit-testable in isolation.
They read state but never write it.
"""

from __future__ import annotations


def trigger_combined_profit(state) -> bool:
    """
    Trigger 1: Combined unrealised profit ceiling — lock in gains.
    When portfolio profit crosses threshold, close everything.
    """
    from config.constants import NUCLEAR_COMBINED_PROFIT_USD

    return state.unrealized_pnl >= NUCLEAR_COMBINED_PROFIT_USD


def trigger_daily_gain_target(state) -> bool:
    """
    Trigger 2: Daily gain target — stop trading after exceptional day.
    15% of starting equity on a single day is exceptional profit.
    """
    daily_pnl = state.realized_pnl + state.unrealized_pnl
    target = state.starting_equity * 0.15
    return daily_pnl >= target


def trigger_loss_protection(state) -> bool:
    """
    Trigger 3: Combined floating loss — protect from basket meltdown.
    When unrealised loss exceeds threshold, exit everything immediately.
    """
    from config.constants import NUCLEAR_LOSS_PROTECTION_USD

    return state.unrealized_pnl <= NUCLEAR_LOSS_PROTECTION_USD


def trigger_daily_loss_limit(state) -> bool:
    """
    Trigger 4: Daily loss limit — hard floor, closes everything.
    4% daily loss is the absolute maximum acceptable drawdown.
    """
    daily_pnl = state.realized_pnl + state.unrealized_pnl
    limit = -(state.starting_equity * 0.04)
    return daily_pnl <= limit


def trigger_market_exhaustion(state) -> bool:
    """
    Trigger 5: Market exhaustion — avg basket RSI extreme + declining PnL.
    RSI < 25 (oversold) or > 75 (overbought) indicates exhaustion.
    """
    return state.avg_basket_rsi < 25 or state.avg_basket_rsi > 75


def trigger_latency_anomaly(state) -> bool:
    """
    Trigger 6: Execution latency anomaly — MT5 bridge degraded.
    When fill latency exceeds threshold, market conditions deteriorated.
    """
    from config.constants import NUCLEAR_LATENCY_THRESHOLD_MS

    return state.last_fill_latency_ms > NUCLEAR_LATENCY_THRESHOLD_MS


def trigger_correlation_spike(state) -> bool:
    """
    Trigger 7: Correlation spike — portfolio effectively undiversified.
    When positions become too correlated, portfolio risk concentrates.
    """
    from config.constants import NUCLEAR_CORRELATION_SPIKE

    return state.avg_pair_correlation > NUCLEAR_CORRELATION_SPIKE


# Ordered list: [reason_str, condition_func]
# Order matters — faster/cheaper checks first
TRIGGERS = [
    ("COMBINED_PROFIT", trigger_combined_profit),
    ("DAILY_GAIN_TARGET", trigger_daily_gain_target),
    ("LOSS_PROTECTION", trigger_loss_protection),
    ("DAILY_LOSS_LIMIT", trigger_daily_loss_limit),
    ("MARKET_EXHAUSTION", trigger_market_exhaustion),
    ("LATENCY_ANOMALY", trigger_latency_anomaly),
    ("CORRELATION_SPIKE", trigger_correlation_spike),
]


def evaluate_triggers(state) -> str | None:
    """
    Evaluate all triggers in order.
    Returns the NuclearReason string of the first triggered condition,
    or None if no trigger fires.

    Args:
        state: PortfolioState object

    Returns:
        NuclearReason string or None
    """
    if not state.open_positions:
        return None  # No positions — nothing to nuclear

    for reason, condition in TRIGGERS:
        try:
            if condition(state):
                return reason
        except Exception:
            continue  # Never crash on a trigger evaluation error

    return None

"""
telegram/formatter.py
Telegram message templates — all formatting logic centralised here.

WHY centralise:
Message format changes (adding emoji, restructuring) should touch
one file only, not hunt through alerts.py and commands.py.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scoring.models import ConfluenceScore, GateDecision
    from nuclear.models import NuclearEvent
    from portfolio.state import PortfolioState


def _get_attr(obj, *names, default=None):
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def format_signal_alert(score: "ConfluenceScore", decision: "GateDecision") -> str:
    """Format a trading signal alert for Telegram."""
    regime = str(_get_attr(score, "regime", default="UNKNOWN"))
    regime_emoji = {
        "TREND": "📈",
        "CHOP": "↔️",
        "BREAKOUT": "🚀",
        "REVERSAL": "🔄",
    }.get(regime, "❓")

    direction = str(_get_attr(score, "direction", default="UNKNOWN")).upper()
    direction_emoji = "🟢 LONG" if direction == "LONG" else "🔴 SHORT"
    decision_value = getattr(decision, "value", str(decision))
    decision_label = "⚡ EXECUTE" if "FULL_AUTO" in str(decision_value) else "👁 WATCH"

    return (
        f"👻 <b>GHOST GRID SIGNAL</b> — {decision_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Symbol:    <code>{_get_attr(score, 'symbol', default='UNKNOWN')}</code>\n"
        f"Direction: {direction_emoji}\n"
        f"H_c Score: <b>{_get_attr(score, 'composite', default=0)}/180</b>\n"
        f"  HMP:  {_get_attr(score, 'hmp', default=0)}  │  HLCP: {_get_attr(score, 'hlcp', default=0)}  │  MPP: {_get_attr(score, 'mpp', default=0)}\n"
        f"Regime:  {regime_emoji} {regime}\n"
        f"Session: {_get_attr(score, 'session', default='UNKNOWN')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_nuclear_alert(event: "NuclearEvent", cooldown=None) -> str:
    """Format a nuclear exit alert for Telegram."""
    cooldown_seconds = getattr(cooldown, "remaining_s", None)
    if cooldown_seconds is not None:
        if cooldown_seconds >= 60:
            cooldown_text = f"Cooldown: {max(1, int(cooldown_seconds / 60))} minutes"
        else:
            cooldown_text = f"Cooldown: {int(cooldown_seconds)}s"
    else:
        cooldown_text = "Cooldown: 15 minutes"

    return (
        f"☢️ <b>NUCLEAR EXIT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Reason:    {_get_attr(event, 'reason', default='UNKNOWN')}\n"
        f"Positions: {_get_attr(event, 'positions_closed', default=0)} closed\n"
        f"PnL:       ${_get_attr(event, 'portfolio_pnl', default=0.0):+.2f}\n"
        f"Equity:    ${_get_attr(event, 'equity_at_fire', default=0.0):.2f}\n"
        f"{cooldown_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_status(state: "PortfolioState") -> str:
    """Format a portfolio status snapshot for Telegram."""
    mode = str(_get_attr(state, "current_mode", "mode", default="UNKNOWN"))
    mode_emoji = "🟢" if mode == "SCALP_NORMAL" else "🟡"
    cb_status = "🔴 PAUSED" if bool(_get_attr(state, "circuit_breaker", default=False)) else "🟢 ACTIVE"
    equity = _get_attr(state, "net_equity", "equity", default=0.0)
    daily_pnl = _get_attr(state, "daily_pnl", default=0.0)
    open_positions = _get_attr(state, "open_position_count", default=0)
    nuclear_count = _get_attr(state, "nuclear_count_today", default=0)
    regime = _get_attr(state, "regime", default="UNKNOWN")

    lines = [
        "📊 <b>GHOST GRID STATUS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Status:    {cb_status}",
        f"Mode:      {mode_emoji} {mode}",
        f"Equity:    ${equity:.2f}",
        f"Daily PnL: ${daily_pnl:+.2f}",
        f"Open:      {open_positions} positions",
        f"Nuclear:   {nuclear_count}× today",
    ]
    if regime != "UNKNOWN":
        lines.append(f"Regime:    {regime}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_position_list(state: "PortfolioState") -> str:
    """Format all open positions for Telegram."""
    if not state.open_positions:
        return "📭 No open positions"

    lines = ["📋 <b>Open Positions</b>\n"]
    for _, sm in state.open_positions.items():
        direction = str(_get_attr(sm, "direction", default="UNKNOWN")).upper()
        dir_emoji = "🟢" if direction == "LONG" else "🔴"
        state_value = _get_attr(sm, "state", default="UNKNOWN")
        if hasattr(state_value, "value"):
            state_value = state_value.value
        lines.append(
            f"{dir_emoji} <code>{_get_attr(sm, 'symbol', default='UNKNOWN')}</code> "
            f"@ {_get_attr(sm, 'entry', default=0.0):.5f} | SL {_get_attr(sm, 'hard_stop', default=0.0):.5f} | "
            f"State: {state_value}"
        )
    return "\n".join(lines)


def format_daily_report(
    state: "PortfolioState", trades_today: int, wins_today: int
) -> str:
    """Format an end-of-day summary report for Telegram."""
    win_rate = (wins_today / trades_today * 100) if trades_today > 0 else 0
    pnl_emoji = "🟢" if _get_attr(state, "daily_pnl", default=0.0) >= 0 else "🔴"

    return (
        f"📅 <b>GHOST GRID — DAILY REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"PnL:       {pnl_emoji} ${_get_attr(state, 'daily_pnl', default=0.0):+.2f}\n"
        f"Equity:    ${_get_attr(state, 'net_equity', default=0.0):.2f}\n"
        f"Trades:    {trades_today} ({wins_today}W / "
        f"{trades_today - wins_today}L)\n"
        f"Win Rate:  {win_rate:.0f}%\n"
        f"Nuclear:   {_get_attr(state, 'nuclear_count_today', default=0)}×\n"
        f"Mode:      {_get_attr(state, 'current_mode', 'mode', default='UNKNOWN')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

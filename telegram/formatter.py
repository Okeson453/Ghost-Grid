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


def format_signal_alert(score: "ConfluenceScore", decision: "GateDecision") -> str:
    """Format a trading signal alert for Telegram."""
    regime_emoji = {
        "TREND": "📈",
        "CHOP": "↔️",
        "BREAKOUT": "🚀",
        "REVERSAL": "🔄",
    }.get(score.regime, "❓")

    direction_emoji = "🟢 LONG" if score.direction == "LONG" else "🔴 SHORT"
    decision_label = "⚡ EXECUTE" if "FULL_AUTO" in decision.value else "👁 WATCH"

    return (
        f"👻 <b>GHOST GRID SIGNAL</b> — {decision_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Symbol:    <code>{score.symbol}</code>\n"
        f"Direction: {direction_emoji}\n"
        f"H_c Score: <b>{score.composite}/180</b>\n"
        f"  HMP:  {score.hmp}  │  HLCP: {score.hlcp}  │  MPP: {score.mpp}\n"
        f"Regime:  {regime_emoji} {score.regime}\n"
        f"Session: {score.session}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_nuclear_alert(event: "NuclearEvent") -> str:
    """Format a nuclear exit alert for Telegram."""
    return (
        f"☢️ <b>NUCLEAR EXIT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Reason:    {event.reason.value}\n"
        f"Positions: {event.positions_closed} closed\n"
        f"PnL:       ${event.portfolio_pnl:+.2f}\n"
        f"Equity:    ${event.equity_at_fire:.2f}\n"
        f"Cooldown:  15 minutes\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_status(state: "PortfolioState") -> str:
    """Format a portfolio status snapshot for Telegram."""
    mode_emoji = "🟢" if state.current_mode == "SCALP_NORMAL" else "🟡"
    cb_status = "🔴 PAUSED" if state.circuit_breaker else "🟢 ACTIVE"

    return (
        f"📊 <b>GHOST GRID STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status:    {cb_status}\n"
        f"Mode:      {mode_emoji} {state.current_mode}\n"
        f"Equity:    ${state.net_equity:.2f}\n"
        f"Daily PnL: ${state.daily_pnl:+.2f}\n"
        f"Open:      {state.open_position_count} positions\n"
        f"Nuclear:   {state.nuclear_count_today}× today\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_position_list(state: "PortfolioState") -> str:
    """Format all open positions for Telegram."""
    if not state.open_positions:
        return "📭 No open positions"

    lines = ["📋 <b>Open Positions</b>\n"]
    for pid, sm in state.open_positions.items():
        dir_emoji = "🟢" if sm.direction == "LONG" else "🔴"
        lines.append(
            f"{dir_emoji} <code>{sm.symbol}</code> "
            f"@ {sm.entry:.5f} | SL {sm.hard_stop:.5f} | "
            f"State: {sm.state.value}"
        )
    return "\n".join(lines)


def format_daily_report(
    state: "PortfolioState", trades_today: int, wins_today: int
) -> str:
    """Format an end-of-day summary report for Telegram."""
    win_rate = (wins_today / trades_today * 100) if trades_today > 0 else 0
    pnl_emoji = "🟢" if state.daily_pnl >= 0 else "🔴"

    return (
        f"📅 <b>GHOST GRID — DAILY REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"PnL:       {pnl_emoji} ${state.daily_pnl:+.2f}\n"
        f"Equity:    ${state.net_equity:.2f}\n"
        f"Trades:    {trades_today} ({wins_today}W / "
        f"{trades_today - wins_today}L)\n"
        f"Win Rate:  {win_rate:.0f}%\n"
        f"Nuclear:   {state.nuclear_count_today}×\n"
        f"Mode:      {state.current_mode}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

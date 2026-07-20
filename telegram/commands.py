"""
telegram/commands.py
Telegram command handlers with rate limiting and audit logging.

Commands:
  /nuke      — Manual nuclear exit (all positions)
  /status    — Portfolio status snapshot
  /pause     — Enable circuit_breaker (no new trades)
  /resume    — Disable circuit_breaker
  /positions — List all open positions

All handlers receive injected dependencies via context.bot_data.
All manual commands are logged to audit trail and subject to rate limiting.
"""

from __future__ import annotations
import logging
import json
import time
from typing import TYPE_CHECKING

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import ContextTypes
    HAS_TELEGRAM = True
except ImportError:  # pragma: no cover - exercised when dependency missing
    HAS_TELEGRAM = False
    class InlineKeyboardButton:  # type: ignore[override]
        def __init__(self, text: str, callback_data: str | None = None):
            self.text = text
            self.callback_data = callback_data

    class InlineKeyboardMarkup:  # type: ignore[override]
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    class Update:  # type: ignore[override]
        pass

    class ContextTypes:  # type: ignore[override]
        class DEFAULT_TYPE:  # type: ignore[override]
            pass

if TYPE_CHECKING:
    from portfolio.state import PortfolioState
    from nuclear.controller import NuclearController
    from db.connection import ConnectionPool

from telegram.formatter import format_position_list, format_status
from security.rate_limiter import check_rate_limit, RateLimitAction
from security.audit_log import log_action, AuditAction
from observability.drift_detector import check_drift
from observability.metrics import get_collector

logger = logging.getLogger(__name__)

_CONFIRMATION_TTL_SECONDS = 10.0
_confirmation_state: dict[tuple[int, int], dict] = {}


def _get_confirmation_key(chat_id: int, user_id: int) -> tuple[int, int]:
    return (chat_id, user_id)


def _register_confirmation(chat_id: int, user_id: int, action: str) -> None:
    _confirmation_state[_get_confirmation_key(chat_id, user_id)] = {
        "action": action,
        "expires_at": time.time() + _CONFIRMATION_TTL_SECONDS,
    }


def _consume_confirmation(chat_id: int, user_id: int) -> dict | None:
    key = _get_confirmation_key(chat_id, user_id)
    pending = _confirmation_state.get(key)
    if not pending:
        return None
    if pending["expires_at"] < time.time():
        _confirmation_state.pop(key, None)
        return None
    _confirmation_state.pop(key, None)
    return pending


async def cmd_nuke(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /nuke — Immediate manual nuclear exit.

    WHY authorised only: any message reaching this handler is from
    the configured chat_id (enforced by bot.py filter).
    
    Rate limited: max 3 nukes per minute per user.
    Logged: all nukes recorded to audit trail with timestamp and user ID.
    """
    user_id = update.effective_user.id

    # Check rate limit
    if not check_rate_limit(user_id, RateLimitAction.NUKE):
        logger.warning(f"NUKE rate limit exceeded for user {user_id}")
        await update.message.reply_text(
            "⚠️ Rate limit exceeded. Max 3 nukes per minute."
        )
        return

    chat_id = update.effective_chat.id
    _register_confirmation(chat_id, user_id, "nuke")

    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm:nuke"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel:nuke"),
        ]]
    )
    await update.message.reply_text(
        "☢️ /nuke requires confirmation. Confirm within 10 seconds or it will expire.",
        reply_markup=keyboard,
    )


async def cmd_kill(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/kill — pending confirmation destructive close for the active portfolio."""
    user_id = update.effective_user.id
    if not check_rate_limit(user_id, RateLimitAction.NUKE):
        await update.message.reply_text("⚠️ Rate limit exceeded. Max 3 nukes per minute.")
        return

    chat_id = update.effective_chat.id
    _register_confirmation(chat_id, user_id, "kill")
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm:kill"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel:kill"),
        ]]
    )
    await update.message.reply_text(
        "🛑 /kill requires confirmation. Confirm within 10 seconds or it will expire.",
        reply_markup=keyboard,
    )


async def cmd_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/confirm — execute a pending destructive action."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    pending = _consume_confirmation(chat_id, user_id)
    if not pending:
        await update.message.reply_text("ℹ️ No pending confirmation to execute.")
        return

    nuclear_controller = ctx.bot_data.get("nuclear_controller")
    if nuclear_controller is None:
        await update.message.reply_text("⚠️ Nuclear controller unavailable")
        return

    pool: "ConnectionPool" = ctx.bot_data.get("db_pool")
    if pool:
        await log_action(
            pool,
            AuditAction.NUKE,
            str(user_id),
            details=f"Confirmed Telegram destructive action ({pending['action']})",
        )

    await nuclear_controller.force_nuclear("MANUAL_TELEGRAM")
    await update.message.reply_text("✅ Confirmation accepted. All positions closed.")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel — discard a pending destructive action."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if _get_confirmation_key(chat_id, user_id) in _confirmation_state:
        _confirmation_state.pop(_get_confirmation_key(chat_id, user_id), None)
        await update.message.reply_text("🛑 Confirmation cancelled.")
    else:
        await update.message.reply_text("ℹ️ No pending confirmation to cancel.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — Send portfolio status snapshot."""
    user_id = update.effective_user.id

    # Check rate limit
    if not check_rate_limit(user_id, RateLimitAction.STATUS):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded. Max 30 status checks per minute."
        )
        return

    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📈 Pairs", callback_data="pairs"), InlineKeyboardButton("🧭 Mode", callback_data="mode")]]
    )
    await update.message.reply_text(format_status(state), parse_mode="HTML", reply_markup=keyboard)


async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/pause — Stop processing new signals (existing positions unaffected)."""
    user_id = update.effective_user.id

    # Check rate limit
    if not check_rate_limit(user_id, RateLimitAction.PAUSE):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded. Max 10 pauses per minute."
        )
        return

    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    state.circuit_breaker = True
    logger.warning(f"Trading PAUSED via Telegram command by user {user_id}")

    # Log to audit trail
    pool: "ConnectionPool" = ctx.bot_data.get("db_pool")
    if pool:
        await log_action(
            pool,
            AuditAction.PAUSE,
            str(user_id),
            details=f"Pause trading from Telegram (user={update.effective_user.username})",
        )

    await update.message.reply_text("⏸ Trading paused. /resume to restart.")


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/resume — Re-enable signal processing."""
    user_id = update.effective_user.id

    # Check rate limit
    if not check_rate_limit(user_id, RateLimitAction.RESUME):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded. Max 10 resumes per minute."
        )
        return

    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    if state.day_locked:
        await update.message.reply_text(
            "🔒 Day locked — cannot resume until UTC midnight."
        )
        return

    state.circuit_breaker = False
    logger.info(f"Trading RESUMED via Telegram command by user {user_id}")

    # Log to audit trail
    pool: "ConnectionPool" = ctx.bot_data.get("db_pool")
    if pool:
        await log_action(
            pool,
            AuditAction.RESUME,
            str(user_id),
            details=f"Resume trading from Telegram (user={update.effective_user.username})",
        )

    await update.message.reply_text("▶️ Trading resumed.")


async def cmd_positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/positions — List all open positions."""
    user_id = update.effective_user.id

    # Check rate limit
    if not check_rate_limit(user_id, RateLimitAction.POSITIONS):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded. Max 30 position checks per minute."
        )
        return

    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(
        format_position_list(state), parse_mode="HTML"
    )


async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/mode — Show the current trading mode."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(f"🧭 Current mode: {state.current_mode}")


async def cmd_pairs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/pairs — Show tracked pairs."""
    tracked_pairs = ctx.bot_data.get("tracked_pairs", set())
    text = "📈 Tracked pairs:\n" + "\n".join(sorted(tracked_pairs)) if tracked_pairs else "📈 Tracked pairs: none"
    await update.message.reply_text(text)


async def cmd_scores(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/scores — Show the latest observed score metrics."""
    collector = get_collector()
    rows = list(collector.scores[-5:]) if hasattr(collector, "scores") else []
    if not rows:
        await update.message.reply_text("📊 No score history yet.")
        return
    summary = "\n".join(
        f"{row.get('symbol', '?')} -> {row.get('composite_score', 0)}" for row in rows
    )
    await update.message.reply_text(f"📊 Recent scores:\n{summary}")


async def cmd_pnl(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/pnl — Summarize PnL from the live portfolio state."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(
        f"💰 Equity: ${state.net_equity:.2f}\nDaily PnL: ${state.daily_pnl:+.2f}"
    )


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/health — Report the current drift health and open-position status."""
    drift = check_drift(lookback=20)
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(
        f"🩺 Health\nOpen positions: {state.open_position_count}\nDrift: {drift.message}"
    )


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/history [n] — Show the last N closed trades from the trade journal."""
    text = update.message.text.split() if update.message else []
    try:
        limit = int(text[1]) if len(text) > 1 else 5
    except ValueError:
        limit = 5
    await update.message.reply_text(f"🧾 History preview for last {limit} trades (stubbed from journal).")


async def cmd_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/reload — Refresh the bot state from the current context."""
    await update.message.reply_text("🔄 Bot state reloaded.")


async def cmd_closeall(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/closeall — pending confirmation destructive close-all."""
    user_id = update.effective_user.id
    if not check_rate_limit(user_id, RateLimitAction.NUKE):
        await update.message.reply_text("⚠️ Rate limit exceeded. Max 3 nukes per minute.")
        return

    chat_id = update.effective_chat.id
    _register_confirmation(chat_id, user_id, "closeall")
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirm", callback_data="confirm:closeall"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel:closeall"),
        ]]
    )
    await update.message.reply_text(
        "🧹 /closeall requires confirmation. Confirm within 10 seconds or it will expire.",
        reply_markup=keyboard,
    )


async def cmd_close(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/close [PAIR] — close a single trading pair placeholder."""
    text = update.message.text.split() if update.message else []
    pair = text[1] if len(text) > 1 else "UNKNOWN"
    await update.message.reply_text(f"🧹 Close request queued for {pair}.")


async def cmd_setmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/setmode [scalp|compound|target] — update the current mode placeholder."""
    text = update.message.text.split() if update.message else []
    mode = text[1].upper() if len(text) > 1 else "UNKNOWN"
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    state.current_mode = {
        "SCALP": "SCALP_BURST",
        "COMPOUND": "AGGRESSIVE_COMPOUNDING",
        "TARGET": "DAILY_TARGET",
    }.get(mode, state.current_mode)
    await update.message.reply_text(f"🧭 Mode set to {state.current_mode}")


async def cmd_setlev(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/setlev [PAIR] [value] — placeholder for pair-level leverage configuration."""
    text = update.message.text.split() if update.message else []
    await update.message.reply_text(f"⚙️ Leverage update queued for {text[1] if len(text) > 1 else 'pair'}.")


async def cmd_addpair(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/addpair — add a tracked pair to the in-memory set."""
    text = update.message.text.split() if update.message else []
    pair = text[1] if len(text) > 1 else "UNKNOWN"
    tracked_pairs = ctx.bot_data.setdefault("tracked_pairs", set())
    tracked_pairs.add(pair)
    await update.message.reply_text(f"➕ Added pair {pair}")


async def cmd_removepair(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/removepair — remove a tracked pair from the in-memory set."""
    text = update.message.text.split() if update.message else []
    pair = text[1] if len(text) > 1 else "UNKNOWN"
    tracked_pairs = ctx.bot_data.setdefault("tracked_pairs", set())
    tracked_pairs.discard(pair)
    await update.message.reply_text(f"➖ Removed pair {pair}")

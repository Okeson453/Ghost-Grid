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
from typing import TYPE_CHECKING

try:
    from telegram import Update
    from telegram.ext import ContextTypes
    HAS_TELEGRAM = True
except ImportError:  # pragma: no cover - exercised when dependency missing
    HAS_TELEGRAM = False

if TYPE_CHECKING:
    from portfolio.state import PortfolioState
    from nuclear.controller import NuclearController
    from db.connection import ConnectionPool

from telegram.formatter import format_position_list, format_status
from security.rate_limiter import check_rate_limit, RateLimitAction
from security.audit_log import log_action, AuditAction

logger = logging.getLogger(__name__)


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

    await update.message.reply_text("☢️ Manual nuclear initiated...")

    nuclear_controller = ctx.bot_data.get("nuclear_controller")
    if nuclear_controller is None:
        await update.message.reply_text("⚠️ Nuclear controller unavailable")
        return

    # Log to audit trail
    pool: "ConnectionPool" = ctx.bot_data.get("db_pool")
    if pool:
        await log_action(
            pool,
            AuditAction.NUKE,
            str(user_id),
            details=f"Manual nuclear from Telegram (user={update.effective_user.username})",
        )

    await nuclear_controller.force_nuclear("MANUAL_TELEGRAM")
    await update.message.reply_text("✅ All positions closed.")


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
    await update.message.reply_text(format_status(state), parse_mode="HTML")


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

"""
telegram/commands.py
Telegram command handlers.

Commands:
  /nuke      — Manual nuclear exit (all positions)
  /status    — Portfolio status snapshot
  /pause     — Enable circuit_breaker (no new trades)
  /resume    — Disable circuit_breaker
  /positions — List all open positions

All handlers receive injected dependencies via context.bot_data.
"""

from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING

try:
    from telegram import Update
    from telegram.ext import ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

if TYPE_CHECKING:
    from portfolio.state import PortfolioState
    from nuclear.controller import NuclearController

from telegram.formatter import format_position_list, format_status

logger = logging.getLogger(__name__)


async def cmd_nuke(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /nuke — Immediate manual nuclear exit.
    
    WHY authorised only: any message reaching this handler is from
    the configured chat_id (enforced by bot.py filter).
    """
    await update.message.reply_text("☢️ Manual nuclear initiated...")
    nuclear_controller: "NuclearController" = ctx.bot_data["nuclear_controller"]
    await nuclear_controller.force_nuclear("MANUAL_TELEGRAM")
    await update.message.reply_text("✅ All positions closed.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — Send portfolio status snapshot."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(format_status(state), parse_mode="HTML")


async def cmd_pause(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/pause — Stop processing new signals (existing positions unaffected)."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    state.circuit_breaker = True
    logger.warning("Trading PAUSED via Telegram command")
    await update.message.reply_text("⏸ Trading paused. /resume to restart.")


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/resume — Re-enable signal processing."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    if state.day_locked:
        await update.message.reply_text(
            "🔒 Day locked — cannot resume until UTC midnight."
        )
        return
    state.circuit_breaker = False
    logger.info("Trading RESUMED via Telegram command")
    await update.message.reply_text("▶️ Trading resumed.")


async def cmd_positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/positions — List all open positions."""
    state: "PortfolioState" = ctx.bot_data["portfolio_state"]
    await update.message.reply_text(
        format_position_list(state), parse_mode="HTML"
    )

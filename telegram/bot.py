"""
telegram/bot.py
Telegram bot setup and command handler registration.

Chat ID filter: all commands validated against configured chat_id.
Only the authorised chat can send commands.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional

try:
    from telegram.ext import Application, CommandHandler, filters
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

if TYPE_CHECKING:
    from portfolio.state import PortfolioState
    from nuclear.controller import NuclearController
    from db.connection import ConnectionPool

from config import get_settings
from telegram.commands import (
    cmd_nuke,
    cmd_status,
    cmd_pause,
    cmd_resume,
    cmd_positions,
    cmd_kill,
    cmd_confirm,
    cmd_cancel,
    cmd_mode,
    cmd_pairs,
    cmd_scores,
    cmd_pnl,
    cmd_health,
    cmd_history,
    cmd_reload,
    cmd_closeall,
    cmd_close,
    cmd_setmode,
    cmd_setlev,
    cmd_addpair,
    cmd_removepair,
)

logger = logging.getLogger(__name__)


def build_application(
    portfolio_state: "PortfolioState",
    nuclear_controller: "NuclearController",
    db_pool: Optional["ConnectionPool"] = None,
) -> Application:
    """
    Build the Telegram bot Application with all command handlers.

    Args:
        portfolio_state:       Live PortfolioState instance
        nuclear_controller:    NuclearController instance
        db_pool:              Optional ConnectionPool for audit logging

    Returns:
        Configured Application (not yet running)
    """
    if not HAS_TELEGRAM:
        raise ImportError(
            "python-telegram-bot not installed. "
            "Install with: pip install python-telegram-bot"
        )

    settings = get_settings()

    app = Application.builder().token(settings.telegram_token).build()

    # Inject dependencies via bot_data
    app.bot_data["portfolio_state"] = portfolio_state
    app.bot_data["nuclear_controller"] = nuclear_controller
    if db_pool:
        app.bot_data["db_pool"] = db_pool

    # Command filter: only respond to the authorised chat ID
    chat_filter = filters.Chat(chat_id=int(settings.telegram_chat_id))

    # Register all command handlers with chat filter
    app.add_handler(CommandHandler("nuke", cmd_nuke, filters=chat_filter))
    app.add_handler(CommandHandler("kill", cmd_kill, filters=chat_filter))
    app.add_handler(CommandHandler("confirm", cmd_confirm, filters=chat_filter))
    app.add_handler(CommandHandler("cancel", cmd_cancel, filters=chat_filter))
    app.add_handler(CommandHandler("status", cmd_status, filters=chat_filter))
    app.add_handler(CommandHandler("pause", cmd_pause, filters=chat_filter))
    app.add_handler(CommandHandler("resume", cmd_resume, filters=chat_filter))
    app.add_handler(CommandHandler("positions", cmd_positions, filters=chat_filter))
    app.add_handler(CommandHandler("mode", cmd_mode, filters=chat_filter))
    app.add_handler(CommandHandler("pairs", cmd_pairs, filters=chat_filter))
    app.add_handler(CommandHandler("scores", cmd_scores, filters=chat_filter))
    app.add_handler(CommandHandler("pnl", cmd_pnl, filters=chat_filter))
    app.add_handler(CommandHandler("health", cmd_health, filters=chat_filter))
    app.add_handler(CommandHandler("history", cmd_history, filters=chat_filter))
    app.add_handler(CommandHandler("reload", cmd_reload, filters=chat_filter))
    app.add_handler(CommandHandler("closeall", cmd_closeall, filters=chat_filter))
    app.add_handler(CommandHandler("close", cmd_close, filters=chat_filter))
    app.add_handler(CommandHandler("setmode", cmd_setmode, filters=chat_filter))
    app.add_handler(CommandHandler("setlev", cmd_setlev, filters=chat_filter))
    app.add_handler(CommandHandler("addpair", cmd_addpair, filters=chat_filter))
    app.add_handler(CommandHandler("removepair", cmd_removepair, filters=chat_filter))

    logger.info("Telegram bot configured")
    return app

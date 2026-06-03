"""
telegram/alerts.py
Outbound alert dispatcher — sends formatted messages to Telegram.

Uses python-telegram-bot async API.
Rate limiting: max 30 messages/second to Telegram API (handled by library).
"""

from __future__ import annotations
import logging
from typing import Optional, TYPE_CHECKING

try:
    from telegram import Bot
    from telegram.error import TelegramError
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

if TYPE_CHECKING:
    from scoring.models import ConfluenceScore, GateDecision
    from nuclear.models import NuclearEvent
    from portfolio.state import PortfolioState

from config import get_settings
from telegram.formatter import (
    format_signal_alert,
    format_nuclear_alert,
    format_status,
    format_daily_report,
)

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def get_bot() -> Bot:
    """Get or create the Telegram bot instance."""
    global _bot
    if _bot is None:
        settings = get_settings()
        _bot = Bot(token=settings.telegram_token)
    return _bot


async def send_signal_alert(score: "ConfluenceScore", decision: "GateDecision") -> None:
    """Send H_c signal alert to Telegram."""
    await _send(format_signal_alert(score, decision))


async def send_nuclear_alert(event: "NuclearEvent") -> None:
    """Send nuclear exit alert to Telegram."""
    await _send(format_nuclear_alert(event))


async def send_status(state: "PortfolioState") -> None:
    """Send portfolio status snapshot to Telegram."""
    await _send(format_status(state))


async def send_daily_report(
    state: "PortfolioState", trades: int, wins: int
) -> None:
    """Send end-of-day summary report to Telegram."""
    await _send(format_daily_report(state, trades, wins))


async def _send(text: str) -> None:
    """
    Core send method — handles errors without crashing.
    
    Never raises exceptions — all errors logged.
    """
    if not HAS_TELEGRAM:
        logger.warning("Telegram not installed — message not sent")
        return

    settings = get_settings()
    try:
        await get_bot().send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.error(f"Telegram send error: {e}")
    except Exception as e:
        logger.error(f"Telegram unexpected error: {e}", exc_info=True)

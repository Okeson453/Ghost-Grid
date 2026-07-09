"""
telegram/alerts.py
Outbound alert dispatcher — sends formatted messages to Telegram.

Uses python-telegram-bot async API.
Rate limiting: light fixed-window limiter implemented in the local Telegram alert path.
"""

from __future__ import annotations
import logging
import time
from collections import deque
from typing import Any, Optional, TYPE_CHECKING

try:
    from .ext import Bot
    from .error import TelegramError
    HAS_TELEGRAM = True
except ImportError:  # pragma: no cover - exercised when dependency missing
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


class TelegramRateLimiter:
    """Simple fixed-window limiter for outbound Telegram messages."""

    def __init__(self, max_messages: int = 4, window_seconds: int = 60) -> None:
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def allow(self, priority: str = "normal") -> bool:
        if priority == "high":
            return True

        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()

        if len(self._timestamps) < self.max_messages:
            self._timestamps.append(now)
            return True
        return False


_rate_limiter = TelegramRateLimiter()


class GhostGridTelegram:
    """Thin adapter matching the design-spec Telegram control interface."""

    async def send_signal_alert(self, score: "ConfluenceScore", decision: "GateDecision") -> None:
        await send_signal_alert(score, decision)

    async def send_nuclear_alert(self, event: "NuclearEvent", cooldown: Optional[Any] = None) -> None:
        await send_nuclear_alert(event, cooldown)

    async def send_status(self, state: "PortfolioState") -> None:
        await send_status(state)

    async def send_daily_report(self, state: "PortfolioState", trades: int, wins: int) -> None:
        await send_daily_report(state, trades, wins)


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


async def send_nuclear_alert(event: "NuclearEvent", cooldown: Optional[Any] = None) -> None:
    """Send nuclear exit alert to Telegram, optionally including cooldown context."""
    await _send(format_nuclear_alert(event, cooldown), priority="high")


async def send_status(state: "PortfolioState") -> None:
    """Send portfolio status snapshot to Telegram."""
    await _send(format_status(state))


async def send_daily_report(
    state: "PortfolioState", trades: int, wins: int
) -> None:
    """Send end-of-day summary report to Telegram."""
    await _send(format_daily_report(state, trades, wins))


async def _send(text: str, priority: str = "normal") -> None:
    """
    Core send method — handles errors without crashing.

    Never raises exceptions — all errors logged.
    """
    if not HAS_TELEGRAM:
        logger.warning("Telegram not installed — message not sent")
        return

    if not _rate_limiter.allow(priority):
        logger.warning("Telegram rate limit hit — message suppressed")
        return

    settings = get_settings()
    try:
        await get_bot().send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="HTML",
        )
    except TelegramError as exc:
        logger.error("Telegram send error: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Telegram unexpected error: %s", exc)

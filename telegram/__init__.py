"""
telegram/
Telegram bot interface for GHOST GRID.

Public API:
  build_application()      — Create and configure the Telegram bot
  send_signal_alert()      — Send trading signal alert
  send_nuclear_alert()     — Send nuclear exit alert
  send_status()            — Send portfolio status
  send_daily_report()      — Send end-of-day report
"""

from .bot import build_application
from .alerts import (
    send_signal_alert,
    send_nuclear_alert,
    send_status,
    send_daily_report,
)

__all__ = [
    "build_application",
    "send_signal_alert",
    "send_nuclear_alert",
    "send_status",
    "send_daily_report",
]

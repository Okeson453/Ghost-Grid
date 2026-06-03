"""
watchdog/thread.py
Independent OS-level watchdog thread.

WHY OS thread (not asyncio task):
asyncio tasks share the event loop. If the loop stalls (deadlock,
exception spiral, long-running computation), asyncio tasks stop running.
An OS thread continues independently and is the system's last resort.

Polls equity every 2 seconds and fires emergency nuclear if daily loss
limit is breached — even if the main loop is stalled.

Started by main.py as a daemon thread — automatically killed on process exit.
"""

from __future__ import annotations
import logging
import threading
import time
from typing import Optional, Callable

from watchdog.emergency import emergency_nuclear_write

logger = logging.getLogger(__name__)

WATCHDOG_POLL_INTERVAL_S = 2.0


class WatchdogThread:
    """
    Daemon thread that independently monitors daily loss limit.

    Accesses PortfolioState via a FrozenPortfolioSnapshot provided by
    a thread-safe getter lambda (set by main.py after state is created).
    """

    def __init__(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="ghost_grid_watchdog",
            daemon=True,  # Dies automatically with main process
        )
        self._stop = threading.Event()
        self._get_snap: Optional[Callable] = None  # Set by main.py

    def set_snapshot_getter(self, getter: Callable) -> None:
        """Called by main.py to wire the portfolio state access."""
        self._get_snap = getter

    def start(self) -> None:
        """Start the watchdog thread."""
        logger.info("Watchdog thread starting")
        self._thread.start()

    def stop(self) -> None:
        """Stop the watchdog thread gracefully."""
        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        """Main watchdog loop — polls every 2 seconds."""
        logger.info("Watchdog thread running")

        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as e:
                logger.error(f"Watchdog poll error: {e}")

            self._stop.wait(WATCHDOG_POLL_INTERVAL_S)

        logger.info("Watchdog thread stopped")

    def _poll(self) -> None:
        """Single poll cycle — check equity limits."""
        if self._get_snap is None:
            return

        snap = self._get_snap()

        # Skip if already locked (main loop handles it)
        if snap.day_locked or snap.circuit_breaker:
            return

        equity = snap.net_equity
        daily_pnl = snap.daily_pnl

        # Thresholds (conservative — match nuclear triggers)
        MAX_DAILY_LOSS = 0.04  # 4% daily loss limit
        MAX_DAILY_GAIN = 0.15  # 15% daily gain target

        # Daily loss limit breach — EMERGENCY NUCLEAR
        if daily_pnl <= -(equity * MAX_DAILY_LOSS):
            logger.critical(
                f"WATCHDOG: daily loss limit breached "
                f"daily_pnl={daily_pnl:.2f} equity={equity:.2f} "
                f"max_loss={-(equity * MAX_DAILY_LOSS):.2f}"
            )
            emergency_nuclear_write()
            return

        # Daily gain target (conservative — allow main loop to handle normally)
        if daily_pnl >= equity * MAX_DAILY_GAIN:
            logger.warning(
                f"WATCHDOG: daily gain target reached "
                f"daily_pnl={daily_pnl:.2f} equity={equity:.2f}"
            )
            # Don't fire nuclear here — main loop handles gracefully


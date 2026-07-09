"""
watchdog/thread.py
Independent OS-level watchdog thread.

The design specification requires a separate OS thread that polls equity
and daily PnL every 2 seconds and fires the emergency stop independently
of the main trading loop. It should not depend on the main loop being
healthy or on any extra state guards beyond the equity thresholds.
"""

from __future__ import annotations
import logging
import threading
from typing import Callable, Optional

from risk.constants import MAX_DAILY_GAIN, MAX_DAILY_LOSS
from watchdog.emergency import emergency_nuclear_write

logger = logging.getLogger(__name__)

WATCHDOG_POLL_INTERVAL_S = 2.0


class WatchdogThread:
    """
    Daemon thread that independently monitors daily risk limits.

    Accesses a portfolio snapshot via a getter supplied by the host process.
    """

    def __init__(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name="ghost_grid_watchdog",
            daemon=True,
        )
        self._stop = threading.Event()
        self._get_snap: Optional[Callable[[], object]] = None
        self._halt_trading: Optional[Callable[[], None]] = None

    def set_snapshot_getter(self, getter: Callable[[], object]) -> None:
        """Wire the portfolio snapshot getter used by the watchdog."""
        self._get_snap = getter

    def set_halt_handler(self, handler: Callable[[], None]) -> None:
        """Provide an optional callback for the daily-gain halt condition."""
        self._halt_trading = handler

    def start(self) -> None:
        """Start the watchdog thread."""
        if self._thread.is_alive():
            return
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
            except Exception as exc:
                logger.error("Watchdog poll error: %s", exc)

            self._stop.wait(WATCHDOG_POLL_INTERVAL_S)

        logger.info("Watchdog thread stopped")

    def _poll(self) -> None:
        """Single poll cycle — check equity risk limits."""
        if self._get_snap is None:
            return

        snap = self._get_snap()
        equity = float(getattr(snap, "net_equity", 0.0))
        daily_pnl = float(getattr(snap, "daily_pnl", 0.0))

        if daily_pnl <= -(equity * MAX_DAILY_LOSS):
            logger.critical(
                "WATCHDOG: daily loss limit breached "
                f"daily_pnl={daily_pnl:.2f} equity={equity:.2f} "
                f"max_loss={-(equity * MAX_DAILY_LOSS):.2f}"
            )
            emergency_nuclear_write()
            return

        if daily_pnl >= equity * MAX_DAILY_GAIN:
            logger.warning(
                "WATCHDOG: daily gain target reached "
                f"daily_pnl={daily_pnl:.2f} equity={equity:.2f}"
            )
            if self._halt_trading is not None:
                self._halt_trading()


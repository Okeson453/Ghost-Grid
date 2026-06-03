"""
bridge/health.py
Heartbeat monitor for pipe health.

Periodically checks time since last heartbeat from MT5. Logs warnings if
heartbeat stale (>10s) and triggers disconnection signal if very stale (>30s).
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .reader import PipeReader


log = logging.getLogger(__name__)


class PipeHealthMonitor:
    """Heartbeat-based pipe health monitor."""

    def __init__(self, pipe_reader: PipeReader) -> None:
        self._reader = pipe_reader
        self.disconnected = False

    async def run(self) -> None:
        """
        Check heartbeat every 5 seconds.
        Logs warnings if stale, marks disconnected if very stale.
        """
        while True:
            try:
                now = time.time()
                last_hb = self._reader.last_heartbeat_ts
                elapsed = now - last_hb

                if elapsed > 30.0:
                    log.critical(
                        f"Heartbeat missing for {elapsed:.1f}s — marking disconnected"
                    )
                    self.disconnected = True

                elif elapsed > 10.0:
                    log.warning(f"Heartbeat stale for {elapsed:.1f}s (expected <5s)")

                await asyncio.sleep(5.0)

            except Exception as e:
                log.error(f"HealthMonitor error: {e}")
                await asyncio.sleep(5.0)

"""
bridge/reconnect.py
Exponential backoff reconnection manager.

Monitors pipe connection and attempts reconnection with exponential backoff
(1s, 2s, 4s, 8s, 16s, 30s max). After N failures, sets pause flag to alert
orchestration layer.
"""

from __future__ import annotations
import asyncio
import logging
import math
from typing import TYPE_CHECKING

from config import (
    RECONNECT_BACKOFF_BASE_S,
    RECONNECT_BACKOFF_MAX_S,
    RECONNECT_MAX_ATTEMPTS,
)

if TYPE_CHECKING:
    from .pipe_client import PipeClient
    from .reader import PipeReader


log = logging.getLogger(__name__)


class ReconnectManager:
    """Exponential backoff reconnection manager."""

    def __init__(
        self,
        pipe_client: PipeClient,
        pipe_reader: PipeReader,
    ) -> None:
        self._pipe = pipe_client
        self._reader = pipe_reader
        self.crash_recovery_signal = asyncio.Event()
        self.pause_flag = False

    async def run(self) -> None:
        """
        Monitor pipe connection and attempt reconnection.
        Runs forever (until cancelled).
        """
        attempt = 0

        while True:
            try:
                # Check if connected
                if not self._pipe.is_connected:
                    # Try to reconnect
                    attempt += 1
                    if attempt > RECONNECT_MAX_ATTEMPTS:
                        log.critical(
                            f"Max reconnection attempts ({RECONNECT_MAX_ATTEMPTS}) exceeded."
                        )
                        self.pause_flag = True
                        # Continue retrying with max backoff
                        await asyncio.sleep(RECONNECT_BACKOFF_MAX_S)
                    else:
                        # Exponential backoff: base * 2^attempt, capped at max
                        backoff = min(
                            RECONNECT_BACKOFF_BASE_S * (2 ** (attempt - 1)),
                            RECONNECT_BACKOFF_MAX_S,
                        )
                        log.info(
                            f"Reconnecting in {backoff:.1f}s (attempt {attempt})..."
                        )
                        await asyncio.sleep(backoff)

                        try:
                            await self._pipe.connect()
                            attempt = 0  # Reset on successful connect
                            self.pause_flag = False
                            self.crash_recovery_signal.set()
                            log.info("Reconnected. Triggering crash recovery.")
                        except Exception as e:
                            log.warning(f"Reconnect failed: {e}")

                else:
                    # Connected — sleep until next check
                    await asyncio.sleep(1.0)

            except Exception as e:
                log.error(f"ReconnectManager error: {e}")
                await asyncio.sleep(1.0)

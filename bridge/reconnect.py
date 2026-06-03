"""
bridge/reconnect.py
Exponential backoff reconnection manager with enterprise features.

Monitors pipe connection and attempts reconnection with exponential backoff
(1s, 2s, 4s, 8s, 16s, 30s max). After N failures, sets pause flag to alert
orchestration layer.

Features:
- Exponential backoff with jitter
- Crash recovery signal for orchestration
- Pause flag for circuit-breaker pattern
- Metrics tracking for connection health
"""

from __future__ import annotations
import asyncio
import logging
import time
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


class ReconnectMetrics:
    """Metrics for reconnection manager."""
    def __init__(self) -> None:
        self.total_reconnect_attempts: int = 0
        self.successful_reconnects: int = 0
        self.failed_reconnects: int = 0
        self.circuit_breaker_opened: int = 0
        self.circuit_breaker_resets: int = 0
        self.total_downtime_s: float = 0.0
        self.last_disconnect_ts: float = 0.0
        self.last_reconnect_ts: float = 0.0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_reconnect_attempts = 0
        self.successful_reconnects = 0
        self.failed_reconnects = 0
        self.circuit_breaker_opened = 0
        self.circuit_breaker_resets = 0
        self.total_downtime_s = 0.0


class ReconnectManager:
    """Exponential backoff reconnection manager with enterprise features."""

    def __init__(
        self,
        pipe_client: PipeClient,
        pipe_reader: PipeReader,
    ) -> None:
        self._pipe = pipe_client
        self._reader = pipe_reader
        self.crash_recovery_signal = asyncio.Event()
        self.pause_flag = False
        self._metrics = ReconnectMetrics()
        self._last_disconnect_ts: float = 0.0

    @property
    def metrics(self) -> ReconnectMetrics:
        """Get reconnect manager metrics."""
        return self._metrics

    async def run(self) -> None:
        """
        Monitor pipe connection and attempt reconnection.
        Runs forever (until cancelled).
        """
        attempt = 0
        last_was_connected = self._pipe.is_connected

        while True:
            try:
                current_is_connected = self._pipe.is_connected

                # Detect state change
                if last_was_connected and not current_is_connected:
                    # Transition to disconnected
                    self._last_disconnect_ts = time.time()
                    self._metrics.last_disconnect_ts = self._last_disconnect_ts
                    log.warning("Pipe connection lost")
                    attempt = 0

                if not current_is_connected:
                    # Try to reconnect
                    attempt += 1
                    self._metrics.total_reconnect_attempts += 1

                    if attempt > RECONNECT_MAX_ATTEMPTS:
                        log.critical(
                            f"Max reconnection attempts ({RECONNECT_MAX_ATTEMPTS}) exceeded. "
                            f"Circuit breaker activated."
                        )
                        self.pause_flag = True
                        self._metrics.circuit_breaker_opened += 1
                        # Continue retrying with max backoff
                        await asyncio.sleep(RECONNECT_BACKOFF_MAX_S)
                    else:
                        # Exponential backoff: base * 2^(attempt-1), capped at max
                        backoff = min(
                            RECONNECT_BACKOFF_BASE_S * (2 ** (attempt - 1)),
                            RECONNECT_BACKOFF_MAX_S,
                        )
                        log.info(
                            f"Reconnecting in {backoff:.1f}s "
                            f"(attempt {attempt}/{RECONNECT_MAX_ATTEMPTS})"
                        )
                        await asyncio.sleep(backoff)

                        try:
                            await self._pipe.connect()
                            attempt = 0  # Reset on successful connect
                            self.pause_flag = False
                            self._metrics.successful_reconnects += 1
                            self._metrics.circuit_breaker_resets += 1
                            
                            # Calculate downtime
                            downtime = time.time() - self._last_disconnect_ts
                            self._metrics.total_downtime_s += downtime
                            self._metrics.last_reconnect_ts = time.time()
                            
                            self.crash_recovery_signal.set()
                            log.info(
                                f"Reconnected after {downtime:.1f}s downtime. "
                                f"Triggering crash recovery."
                            )
                        except Exception as e:
                            self._metrics.failed_reconnects += 1
                            log.warning(f"Reconnect failed (attempt {attempt}): {e}")
                else:
                    # Connected — sleep until next check
                    if attempt > 0:
                        # We were reconnecting, now we're connected
                        attempt = 0
                    last_was_connected = True
                    await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                log.info("Reconnect manager cancelled")
                raise
            except Exception as e:
                self._metrics.failed_reconnects += 1
                log.error(f"ReconnectManager error: {e}")
                await asyncio.sleep(1.0)

            last_was_connected = current_is_connected

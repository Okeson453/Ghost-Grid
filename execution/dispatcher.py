"""
execution/dispatcher.py
Named pipe writer for ORDER and CLOSE commands.
WHY: Isolates pipe I/O, enables metrics tracking, provides retry interface.
"""

from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Any

from bridge.protocol import (
    build_close_command,
    build_nuclear_command,
    build_order_command,
)
from .models import ExecutionCommand, DispatchMetrics

logger = logging.getLogger(__name__)


class PipeDispatcher:
    """
    Write ORDER and CLOSE commands to MT5 via named pipe.
    WHY: Atomicity and metrics enable failure recovery.
    """

    def __init__(self, pipe_path: str, pipe_client: Optional[Any] = None):
        self.pipe_path = Path(pipe_path)
        self._metrics = DispatchMetrics()
        self._pipe_client = pipe_client
        self.last_response: Optional[str] = None

    async def dispatch(self, command: ExecutionCommand, timeout_s: float = 5.0) -> bool:
        """
        Write command to pipe. Return True if successful.
        WHY: Return bool enables retry logic to decide on re-attempt.
        """
        try:
            self._metrics.orders_sent += 1 if command.command_type == "ORDER" else 0
            self._metrics.closes_sent += 1 if command.command_type == "CLOSE" else 0

            if command.command_type == "ORDER":
                command_str = build_order_command(
                    position_id=str(command.position_id or 0),
                    symbol=command.symbol,
                    direction=command.direction or "LONG",
                    lot_size=command.lot_size or 0.0,
                    entry_price=command.entry_price or 0.0,
                    stop_loss=0.0,
                )
            elif command.command_type == "CLOSE":
                command_str = build_close_command(str(command.position_id or 0))
            else:
                command_str = build_nuclear_command()

            if os.getenv("PAPER_MODE", "true").lower() == "true":
                logger.info("PAPER_MODE dispatch: %s", command_str.strip())
                self.last_response = None
                return True

            await asyncio.wait_for(
                self._write_to_pipe(command_str),
                timeout=timeout_s,
            )
            self._metrics.bytes_written += len(command_str.encode())
            self.last_response = await self._read_response(timeout_s)
            return True

        except asyncio.TimeoutError:
            self._metrics.pipe_timeouts += 1
            self._metrics.dispatch_errors += 1
            return False
        except Exception as e:
            self._metrics.dispatch_errors += 1
            return False

    async def _write_to_pipe(self, data: str) -> None:
        """
        Write data to named pipe asynchronously.
        WHY: Async I/O prevents blocking main event loop.
        """
        try:
            # Prefer injected async PipeClient (uses win32). If not provided,
            # lazily create one so we never fall back to opening a regular file.
            if self._pipe_client is None:
                try:
                    from bridge.pipe_client import PipeClient

                    self._pipe_client = PipeClient()
                except Exception as ex:
                    raise RuntimeError(f"Failed to construct PipeClient: {ex}")

            await self._pipe_client.connect()
            success = await self._pipe_client.writeline(data)
            if not success:
                raise RuntimeError("Pipe client write failed")
            return
        except Exception as e:
            raise RuntimeError(f"Pipe write failed: {e}")

    async def _read_response(self, timeout_s: float) -> Optional[str]:
        """Read a single response line from the pipe client if available."""
        if self._pipe_client is None:
            return None

        try:
            return await asyncio.wait_for(self._pipe_client.readline(), timeout=timeout_s)
        except (asyncio.TimeoutError, Exception):
            return None

    def _sync_write_to_pipe(self, data: str) -> None:
        """Synchronous pipe write (called in executor)."""
        # Legacy fallback removed: synchronous file-based pipe writes are
        # unsafe on Windows named pipes. Use PipeClient instead.
        raise RuntimeError(
            "Synchronous file-based pipe write is unsupported; use PipeClient"
        )

    @property
    def metrics(self) -> DispatchMetrics:
        """Expose metrics."""
        return self._metrics


# Backwards-compatible name expected by older imports
Dispatcher = PipeDispatcher

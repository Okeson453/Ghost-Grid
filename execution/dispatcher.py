"""
execution/dispatcher.py
Named pipe writer for ORDER and CLOSE commands.
WHY: Isolates pipe I/O, enables metrics tracking, provides retry interface.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional

from .models import ExecutionCommand, DispatchMetrics


class PipeDispatcher:
    """
    Write ORDER and CLOSE commands to MT5 via named pipe.
    WHY: Atomicity and metrics enable failure recovery.
    """

    def __init__(self, pipe_path: str):
        self.pipe_path = Path(pipe_path)
        self._metrics = DispatchMetrics()

    async def dispatch(self, command: ExecutionCommand, timeout_s: float = 5.0) -> bool:
        """
        Write command to pipe. Return True if successful.
        WHY: Return bool enables retry logic to decide on re-attempt.
        """
        try:
            self._metrics.orders_sent += 1 if command.command_type == "ORDER" else 0
            self._metrics.closes_sent += 1 if command.command_type == "CLOSE" else 0

            # Build command string based on type
            if command.command_type == "ORDER":
                command_str = (
                    f"ORDER|{command.symbol}|{command.direction}|"
                    f"{command.lot_size}|{command.entry_price}|"
                    f"{command.metadata}\n"
                )
            else:  # CLOSE
                command_str = (
                    f"CLOSE|{command.symbol}|{command.position_id}|"
                    f"{command.exit_reason}\n"
                )

            # Write to pipe with timeout
            await asyncio.wait_for(
                self._write_to_pipe(command_str),
                timeout=timeout_s,
            )
            self._metrics.bytes_written += len(command_str.encode())
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
            # In production, this would use async pipe I/O (e.g., aiofiles + async pipe)
            # For now, use sync write wrapped in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._sync_write_to_pipe,
                data,
            )
        except Exception as e:
            raise RuntimeError(f"Pipe write failed: {e}")

    def _sync_write_to_pipe(self, data: str) -> None:
        """Synchronous pipe write (called in executor)."""
        try:
            # Open pipe for writing (named pipe must exist)
            with open(str(self.pipe_path), "w") as pipe:
                pipe.write(data)
                pipe.flush()
        except FileNotFoundError:
            raise RuntimeError(f"Pipe not found: {self.pipe_path}")
        except Exception as e:
            raise RuntimeError(f"Pipe write failed: {e}")

    @property
    def metrics(self) -> DispatchMetrics:
        """Expose metrics."""
        return self._metrics

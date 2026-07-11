"""
bridge/pipe_client.py
Async Windows Named Pipe client with enterprise-grade resource management.

Wraps win32file API to communicate with MT5 EA over a named pipe.
Connection is established on-demand and persists across multiple read/write cycles.
Handles reconnection with exponential backoff (managed by ReconnectManager).

Features:
- Metrics tracking for connection health monitoring
- Automatic cleanup and resource management
- Per-operation locks to prevent concurrent access
- Comprehensive error logging and reporting
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

import pywintypes
import win32file
import win32pipe
import winerror

from config import get_settings


log = logging.getLogger(__name__)


class PipeClientMetrics:
    """Metrics for pipe client health and performance."""

    def __init__(self) -> None:
        self.connection_attempts: int = 0
        self.connection_failures: int = 0
        self.connection_successes: int = 0
        self.total_reads: int = 0
        self.total_writes: int = 0
        self.read_errors: int = 0
        self.write_errors: int = 0
        self.bytes_read: int = 0
        self.bytes_written: int = 0
        self.last_read_ts: float = 0.0
        self.last_write_ts: float = 0.0
        self.uptime_s: float = 0.0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.connection_attempts = 0
        self.connection_failures = 0
        self.connection_successes = 0
        self.total_reads = 0
        self.total_writes = 0
        self.read_errors = 0
        self.write_errors = 0
        self.bytes_read = 0
        self.bytes_written = 0


class PipeClient:
    """Async Named Pipe client for MT5 communication with enterprise features."""

    def __init__(self, pipe_path: Optional[str] = None) -> None:
        # Allow overriding the pipe path for dual-pipe setups
        self._pipe_path = pipe_path if pipe_path is not None else get_settings().pipe_path
        self._handle: Optional[pywintypes.HANDLE] = None
        self._connected = asyncio.Event()
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._metrics = PipeClientMetrics()
        self._connection_start_time: Optional[float] = None

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to pipe."""
        return self._connected.is_set()

    @property
    def metrics(self) -> PipeClientMetrics:
        """Get client metrics for monitoring."""
        if self._connection_start_time:
            self._metrics.uptime_s = time.time() - self._connection_start_time
        return self._metrics

    async def connect(self) -> None:
        """
        Open connection to MT5 pipe server.

        Raises: Exception if connection fails after retries.
        """
        self._metrics.connection_attempts += 1
        loop = asyncio.get_event_loop()
        try:
            self._handle = await loop.run_in_executor(None, self._open_pipe)
            self._connected.set()
            self._connection_start_time = time.time()
            self._metrics.connection_successes += 1
            log.info(
                f"Connected to MT5 pipe: {self._pipe_path} "
                f"(attempt #{self._metrics.connection_attempts})"
            )
        except Exception as e:
            self._metrics.connection_failures += 1
            # Avoid passing non-standard kwargs to the stdlib logger
            log.error(f"Failed to connect to pipe: {e} (attempt={self._metrics.connection_attempts})")
            self._connected.clear()
            raise

    def _open_pipe(self) -> pywintypes.HANDLE:
        """
        Blocking pipe open. Retries on FILE_NOT_FOUND with 1s sleep
        until MT5 opens the pipe server.

        WHY retry: MT5 EA may not have opened the pipe server yet when
        Python starts. Graceful retry avoids startup race condition.
        """
        retry_count = 0
        max_retries = 30  # 30 seconds max wait

        while retry_count < max_retries:
            try:
                handle = win32file.CreateFile(
                    self._pipe_path,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                log.debug(f"Pipe opened after {retry_count} retries")
                return handle
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    retry_count += 1
                    if retry_count % 5 == 0:  # Log every 5 retries
                        log.debug(f"Pipe not ready, retrying ({retry_count}s)...")
                    time.sleep(1)
                else:
                    raise

        raise RuntimeError(f"Pipe server not ready after {max_retries} seconds")

    async def readline(self) -> Optional[str]:
        """
        Read one line from pipe (async).
        Returns None on connection error or empty data.
        Tracks read metrics.
        """
        if not self.is_connected or self._handle is None:
            return None

        loop = asyncio.get_event_loop()
        async with self._read_lock:
            try:
                data = await loop.run_in_executor(None, self._blocking_read)
                if data:
                    self._metrics.total_reads += 1
                    self._metrics.bytes_read += len(data)
                    self._metrics.last_read_ts = time.time()
                    return data.decode("utf-8", errors="ignore").strip()
                return None
            except Exception as e:
                self._metrics.read_errors += 1
                log.error(f"Read error: {e}")
                self._connected.clear()
                return None

    def _blocking_read(self) -> bytes:
        """Blocking read from pipe with error handling."""
        if self._handle is None:
            raise ConnectionError("Pipe not connected")
        try:
            _, data = win32file.ReadFile(self._handle, 4096)
            return data
        except pywintypes.error as e:
            log.error(f"win32 read error: {e}")
            raise

    async def writeline(self, message: str) -> bool:
        """
        Write one line to pipe (async).
        Returns False on connection error.
        Tracks write metrics.
        """
        if not self.is_connected or self._handle is None:
            return False

        loop = asyncio.get_event_loop()
        async with self._write_lock:
            try:
                await loop.run_in_executor(None, self._blocking_write, message)
                self._metrics.total_writes += 1
                self._metrics.bytes_written += len(message) + 1  # +1 for newline
                self._metrics.last_write_ts = time.time()
                return True
            except Exception as e:
                self._metrics.write_errors += 1
                log.error(f"Write error: {e}")
                self._connected.clear()
                return False

    def _blocking_write(self, message: str) -> None:
        """Blocking write to pipe with error handling."""
        if self._handle is None:
            raise ConnectionError("Pipe not connected")
        try:
            data = (message + "\n").encode("utf-8")
            win32file.WriteFile(self._handle, data)
        except pywintypes.error as e:
            log.error(f"win32 write error: {e}")
            raise

    async def close(self) -> None:
        """Close pipe connection and cleanup resources."""
        self._connected.clear()
        if self._handle is not None:
            try:
                win32file.CloseHandle(self._handle)
                log.info(
                    "Pipe closed",
                    uptime_s=self._metrics.uptime_s,
                    total_reads=self._metrics.total_reads,
                    total_writes=self._metrics.total_writes,
                )
            except Exception as e:
                log.warning(f"Error closing pipe: {e}")
            finally:
                self._handle = None
                self._connection_start_time = None
    async def write(self, message: str) -> bool:
        """
        Convenience alias that ensures connection then writes a line.
        Kept for backwards compatibility with callers using `write()`.
        """
        if not self.is_connected:
            try:
                await self.connect()
            except Exception:
                return False
        return await self.writeline(message)

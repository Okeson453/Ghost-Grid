"""
bridge/pipe_client.py
Async Windows Named Pipe client.

Wraps win32pipe.popen2() to communicate with MT5 EA over a named pipe.
Connection is established on-demand and persists across multiple read/write cycles.
Handles reconnection with exponential backoff (managed by ReconnectManager).
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


class PipeClient:
    """Async Named Pipe client for MT5 communication."""

    def __init__(self) -> None:
        self._pipe_path = get_settings().pipe_path
        self._handle: Optional[pywintypes.HANDLE] = None
        self._connected = asyncio.Event()
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to pipe."""
        return self._connected.is_set()

    async def connect(self) -> None:
        """Open connection to MT5 pipe server."""
        loop = asyncio.get_event_loop()
        try:
            self._handle = await loop.run_in_executor(
                None, self._open_pipe
            )
            self._connected.set()
            log.info(f"Connected to MT5 pipe: {self._pipe_path}")
        except Exception as e:
            log.error(f"Failed to connect to pipe: {e}")
            self._connected.clear()
            raise

    def _open_pipe(self) -> pywintypes.HANDLE:
        """
        Blocking pipe open. Retries on FILE_NOT_FOUND (2) with 1s sleep
        until MT5 opens the pipe server.
        
        WHY retry: MT5 EA may not have opened the pipe server yet when
        Python starts. Graceful retry avoids startup race condition.
        """
        while True:
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
                return handle
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    log.debug(f"Pipe not ready, retrying in 1s...")
                    time.sleep(1)
                else:
                    raise

    async def readline(self) -> Optional[str]:
        """
        Read one line from pipe (async).
        Returns None on connection error.
        """
        if not self.is_connected or self._handle is None:
            return None

        loop = asyncio.get_event_loop()
        async with self._read_lock:
            try:
                data = await loop.run_in_executor(
                    None, self._blocking_read
                )
                if data:
                    return data.decode("utf-8", errors="ignore").strip()
                return None
            except Exception as e:
                log.error(f"Read error: {e}")
                self._connected.clear()
                return None

    def _blocking_read(self) -> bytes:
        """Blocking read from pipe."""
        if self._handle is None:
            return b""
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
        """
        if not self.is_connected or self._handle is None:
            return False

        loop = asyncio.get_event_loop()
        async with self._write_lock:
            try:
                await loop.run_in_executor(
                    None, self._blocking_write, message
                )
                return True
            except Exception as e:
                log.error(f"Write error: {e}")
                self._connected.clear()
                return False

    def _blocking_write(self, message: str) -> None:
        """Blocking write to pipe."""
        if self._handle is None:
            raise ConnectionError("Pipe not connected")
        try:
            data = (message + "\n").encode("utf-8")
            win32file.WriteFile(self._handle, data)
        except pywintypes.error as e:
            log.error(f"win32 write error: {e}")
            raise

    async def close(self) -> None:
        """Close pipe connection."""
        self._connected.clear()
        if self._handle is not None:
            try:
                win32file.CloseHandle(self._handle)
            except Exception as e:
                log.warning(f"Error closing pipe: {e}")
            self._handle = None

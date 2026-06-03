"""
watchdog/emergency.py
Emergency pipe writer — OS thread safe, asyncio-independent.

WHY bypass asyncio:
If the main asyncio event loop deadlocks or stalls, the watchdog
cannot await pipe operations. It must write synchronously.

This is the last line of defence.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def emergency_nuclear_write(pipe_path: str = r"\\.\pipe\ghost_grid_commands") -> bool:
    """
    Write NUCLEAR_ALL command to the pipe synchronously.
    Does NOT wait for confirmation — fire and forget.
    
    Args:
        pipe_path: Windows named pipe path
        
    Returns:
        True if write succeeded
    """
    try:
        import win32file
        import pywintypes
    except ImportError:
        logger.critical("emergency_nuclear_write: win32 not available (non-Windows)")
        return False

    cmd = b"V1|NUCLEAR_ALL\n"

    try:
        handle = win32file.CreateFile(
            pipe_path,
            win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None,
        )
        win32file.WriteFile(handle, cmd)
        win32file.CloseHandle(handle)
        logger.critical("Emergency NUCLEAR_ALL sent via sync pipe write")
        return True
    except Exception as e:
        logger.critical(f"Emergency pipe write failed: {e}")
        return False

"""
watchdog/emergency.py
Emergency pipe writer — OS thread safe, asyncio-independent.

The design specification requires a synchronous named-pipe write that
bypasses the main event loop. It uses the MT5 bridge pipe directly and
sends the plain NUCLEAR_ALL\n payload.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

DEFAULT_PIPE_PATH = r"\\.\pipe\ghostgrid"
DEFAULT_NUCLEAR_PAYLOAD = b"NUCLEAR_ALL\n"


def emergency_nuclear_write(
    pipe_path: str = DEFAULT_PIPE_PATH,
    payload: bytes = DEFAULT_NUCLEAR_PAYLOAD,
) -> bool:
    """
    Write the emergency stop command to the named pipe synchronously.

    The message is fire-and-forget: the function returns as soon as the
    write attempt completes, without waiting for confirmation.
    """
    try:
        with open(pipe_path, "r+b", buffering=0) as pipe_handle:
            pipe_handle.write(payload)
            pipe_handle.flush()
        logger.critical("Emergency NUCLEAR_ALL sent via sync pipe write")
        return True
    except (FileNotFoundError, OSError, ValueError) as exc:
        logger.critical("Emergency pipe write failed: %s", exc)
        return False

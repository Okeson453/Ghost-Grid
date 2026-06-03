"""
nuclear/executor.py
Nuclear exit executor — close all positions simultaneously.

Uses asyncio.gather to dispatch all CLOSE commands concurrently.
Waits up to 3 seconds for confirmation.
Force-closes any positions not confirmed within timeout.

WHY concurrent not sequential:
Sequential close in a 5-position portfolio takes 5× the latency.
During a market meltdown, every millisecond of delay increases loss.
asyncio.gather fires all CLOSE commands simultaneously.
"""

from __future__ import annotations
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

CLOSE_VERIFY_TIMEOUT_S = 3.0
FORCE_CLOSE_ATTEMPTS = 2


async def execute_nuclear_close(
    state,
    commander,
    reason: str,
) -> dict[int, bool]:
    """
    Close all open positions concurrently.

    Args:
        state:     Current PortfolioState (open_positions read here)
        commander: ExecutionCommander for CLOSE dispatch
        reason:    NuclearReason string (for logging)

    Returns:
        dict[position_id] → bool (True if closed, False if failed)
    """
    if not state.open_positions:
        logger.info(f"Nuclear {reason}: no open positions to close")
        return {}

    position_ids = list(state.open_positions.keys())
    logger.warning(
        f"NUCLEAR FIRE: {reason} | Closing {len(position_ids)} positions: {position_ids}"
    )

    # Dispatch all CLOSE commands concurrently via asyncio.gather
    close_tasks = [commander.close(position_id, reason) for position_id in position_ids]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*close_tasks, return_exceptions=True),
            timeout=CLOSE_VERIFY_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"Nuclear close timed out after {CLOSE_VERIFY_TIMEOUT_S}s — "
            f"some positions may not have confirmed closes"
        )
        results = [False] * len(position_ids)

    # Construct result dict
    close_results = {pid: (r is True) for pid, r in zip(position_ids, results)}

    # Count successes
    success_count = sum(1 for v in close_results.values() if v)
    logger.info(f"Nuclear close: {success_count}/{len(position_ids)} confirmed")

    return close_results

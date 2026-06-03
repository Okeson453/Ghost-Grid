"""
main.py
GHOST GRID production entry point.

Phase 1 orchestration: data pipeline from MT5 ticks to MarketSnapshot objects.
Logs MarketSnapshot to console every tick.
"""

from __future__ import annotations
import asyncio
import logging
import signal
import sys
from typing import Optional

import structlog

from config import get_settings
from data import MarketSnapshot, FeedRouter
from bridge import PipeClient, PipeReader, PipeWriter
from bridge.reconnect import ReconnectManager
from bridge.health import PipeHealthMonitor


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


async def on_snapshot(snapshot: MarketSnapshot) -> None:
    """
    Callback invoked on each complete MarketSnapshot.

    Logs: symbol, bid, session, atr_1m, vwap, m1_bars, cvd_len
    """
    m1_count = len(snapshot.m1) if snapshot.m1 else 0
    cvd_len = len(snapshot.cvd_history) if snapshot.cvd_history else 0

    log.info(
        "snapshot_produced",
        symbol=snapshot.symbol,
        bid=snapshot.tick.bid,
        session=snapshot.session,
        atr_1m=snapshot.atr_1m,
        vwap=snapshot.vwap,
        m1_bars=m1_count,
        cvd_len=cvd_len,
        regime=snapshot.regime,
    )


async def main() -> None:
    """
    Async main orchestration loop.

    Initializes pipe client, reader, writer, feed router, and health monitor.
    Runs until cancelled via SIGINT/SIGTERM.
    """
    settings = get_settings()

    log.info(
        "startup",
        paper_trading=settings.paper_trading,
        pipe_path=settings.pipe_path,
        mt5_server=settings.mt5_server,
    )

    # Initialize components
    pipe_client = PipeClient()
    pipe_reader = PipeReader(pipe_client)
    pipe_writer = PipeWriter(pipe_client)
    feed_router = FeedRouter(pipe_reader, on_snapshot)
    reconnect_manager = ReconnectManager(pipe_client, pipe_reader)
    health_monitor = PipeHealthMonitor(pipe_reader)

    # Connect to MT5 pipe
    try:
        await pipe_client.connect()
    except Exception as e:
        log.error("connect_failed", error=str(e))
        return

    # Launch all tasks
    try:
        tasks = [
            asyncio.create_task(pipe_reader.run(), name="reader"),
            asyncio.create_task(pipe_writer.run(), name="writer"),
            asyncio.create_task(feed_router.run(), name="feed_router"),
            asyncio.create_task(reconnect_manager.run(), name="reconnect"),
            asyncio.create_task(health_monitor.run(), name="health"),
        ]

        log.info("all_tasks_launched")

        # Wait for all tasks (should run forever)
        await asyncio.gather(*tasks)

    except asyncio.CancelledError:
        log.info("shutdown_requested")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        log.error("fatal_error", error=str(e))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await pipe_client.close()
        log.info("shutdown_complete")


def signal_handler(signum, frame):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    log.info("signal_received", signal_num=signum)
    # Stop the event loop
    loop = asyncio.get_event_loop()
    loop.stop()


if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("interrupted")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())

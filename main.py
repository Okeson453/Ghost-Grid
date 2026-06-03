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
    Periodically logs metrics for enterprise monitoring.
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

    # Metrics reporting task
    async def report_metrics() -> None:
        """Periodically report bridge, pipe, and data layer metrics."""
        while True:
            try:
                await asyncio.sleep(30.0)  # Report every 30 seconds
                
                # Bridge metrics
                client_metrics = pipe_client.metrics
                reader_metrics = pipe_reader.metrics
                writer_metrics = pipe_writer.metrics
                reconnect_metrics = reconnect_manager.metrics
                
                # Data layer metrics (collect from all symbol builders)
                total_snapshots = feed_router._metrics.total_snapshots
                callback_errors = feed_router._metrics.callback_errors
                agg_m1_bars = sum(b.metrics.m1_bars_created for b in feed_router._builders.values())
                agg_m5_bars = sum(b.metrics.m5_bars_created for b in feed_router._builders.values())
                snapshot_warmups = sum(b.metrics.warmup_ticks for b in feed_router._builders.values())
                
                log.info(
                    "metrics_report",
                    # Pipe client
                    client_connects=client_metrics.connection_successes,
                    client_uptime_s=client_metrics.uptime_s,
                    client_reads=client_metrics.total_reads,
                    client_writes=client_metrics.total_writes,
                    # Reader
                    reader_lines_read=reader_metrics.total_lines_read,
                    reader_ticks=reader_metrics.ticks_dispatched,
                    reader_fills=reader_metrics.fills_dispatched,
                    reader_tick_overflows=reader_metrics.tick_queue_overflows,
                    # Writer
                    writer_enqueued=writer_metrics.total_enqueued,
                    writer_written=writer_metrics.total_written,
                    writer_queue_depth=writer_metrics.max_queue_depth,
                    writer_overflows=writer_metrics.queue_overflows,
                    # Reconnect
                    reconnect_attempts=reconnect_metrics.total_reconnect_attempts,
                    reconnect_successes=reconnect_metrics.successful_reconnects,
                    downtime_s=reconnect_metrics.total_downtime_s,
                    # Data layer
                    total_snapshots=total_snapshots,
                    callback_errors=callback_errors,
                    m1_bars_created=agg_m1_bars,
                    m5_bars_created=agg_m5_bars,
                    warmup_ticks=snapshot_warmups,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("metrics_report_error", error=str(e))

    # Launch all tasks
    try:
        tasks = [
            asyncio.create_task(pipe_reader.run(), name="reader"),
            asyncio.create_task(pipe_writer.run(), name="writer"),
            asyncio.create_task(feed_router.run(), name="feed_router"),
            asyncio.create_task(reconnect_manager.run(), name="reconnect"),
            asyncio.create_task(health_monitor.run(), name="health"),
            asyncio.create_task(report_metrics(), name="metrics_reporter"),
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
        # Log final metrics
        client_metrics = pipe_client.metrics
        reader_metrics = pipe_reader.metrics
        writer_metrics = pipe_writer.metrics
        feed_metrics = feed_router.metrics
        
        log.info(
            "shutdown_complete",
            client_uptime_s=client_metrics.uptime_s,
            total_ticks=reader_metrics.ticks_dispatched,
            total_writes=writer_metrics.total_written,
            total_snapshots=feed_metrics.total_snapshots,
            callback_errors=feed_metrics.callback_errors,
        )
        await pipe_client.close()


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

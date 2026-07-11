from __future__ import annotations
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
try:
    import structlog
except Exception:  # pragma: no cover - fallback when structlog not available
    structlog = None
from config import get_settings
from config.instruments import get_instrument
from bridge.pipe_client import PipeClient
from bridge.reader import PipeReader
from bridge.writer import PipeWriter
from bridge.reconnect import ReconnectManager
from data.feed_router import FeedRouter
from data.schema import MarketSnapshot
from db.connection import get_async_connection, run_migrations
from db.recovery import (
    get_open_positions_from_db,
    get_next_position_id,
)
from db.writer import write_h_score, write_position_opened
from scoring.fusion import score_confluence
from scoring.gate import ConfluenceGate
from scoring.models import GateDecision
from risk.governor import RiskGovernor
from risk.models import ProposedOrder, PortfolioSnapshot as RiskPortfolioSnapshot
from risk.sizer import compute_stop_loss
from execution.commander import ExecutionCommander
from execution.dispatcher import Dispatcher
from execution.fill_handler import FillHandler
from execution.leverage import compute_leverage
from execution.models import ValidatedOrder
from positions.state_machine import PositionStateMachine
from positions.registry import PositionRegistry
from portfolio.state import PortfolioState
from portfolio.ledger import Ledger
from nuclear.controller import NuclearController
from watchdog.thread import WatchdogThread
from telegram.bot import build_application
from telegram.alerts import send_signal_alert, send_nuclear_alert, _send
from observability.metrics import record_score
from observability.drift_detector import check_drift
from observability.trade_journal import record_opened, record_closed
from observability.daily_report import generate_daily_report

# ── Logging ────────────────────────────────────────────────────────────────
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()


# ── Global state (injected at startup, read everywhere) ────────────────────
portfolio_state: Optional[PortfolioState] = None
nuclear_controller: Optional[NuclearController] = None
position_registry: Optional[PositionRegistry] = None
gate: Optional[ConfluenceGate] = None
risk_governor: Optional[RiskGovernor] = None
commander: Optional[ExecutionCommander] = None
ledger: Optional[Ledger] = None
_shutdown_event = asyncio.Event()
_current_prices: dict[str, float] = {}
_pos_id_counter = 1


# ── Scoring pipeline callback ──────────────────────────────────────────────


async def on_snapshot(snap: MarketSnapshot) -> None:
    """
    Called by FeedRouter for every MarketSnapshot.
    Runs the full H_c scoring + gate + risk + execution pipeline.
    """
    global portfolio_state, gate, risk_governor, commander, position_registry
    global ledger, _current_prices

    # Track current price for portfolio PnL calculation
    _current_prices[snap.symbol] = snap.tick.mid

    # ── Skip if circuit breaker active ────────────────────────────────────
    if portfolio_state and portfolio_state.circuit_breaker:
        return

    # ── Update existing positions on tick ─────────────────────────────────
    if position_registry and portfolio_state and commander and ledger:
        exits = await position_registry.process_tick(snap, portfolio_state)
        # Handle any exits triggered by state machine updates
        for position_id, exit_reason in exits:
            pos = position_registry.get_position(position_id)
            if pos:
                realized_pnl = pos._calc_pnl(snap.tick.mid)
                await commander.close_position(snap.symbol, position_id, exit_reason)
                # Record to trade journal
                try:
                    record_closed(
                        position_id=position_id,
                        symbol=pos.symbol,
                        direction=pos.direction,
                        entry_price=pos.entry,
                        exit_price=snap.tick.mid,
                        lot_size=pos.lots,
                        realized_pnl=realized_pnl,
                        exit_reason=str(exit_reason),
                    )
                except Exception as e:
                    log.error("trade_journal_close_error", position_id=position_id, error=str(e))
                position_registry.remove_position(
                    position_id, realized_pnl, portfolio_state
                )

    # ── Score new signal ─────────────────────────────────────────────────
    try:
        score = score_confluence(snap)
        decision = gate.evaluate(score) if gate else GateDecision.DISCARD
    except Exception as e:
        log.error("scoring_error", symbol=snap.symbol, error=str(e))
        return

    # ── Persist score to DB ──────────────────────────────────────────────
    try:
        await write_h_score(
            symbol=score.symbol,
            hmp=score.hmp,
            hlcp=score.hlcp,
            mpp=score.mpp,
            composite=score.composite,
            direction=score.direction,
            regime=score.regime,
            gate_decision=decision.value,
            timestamp_ms=score.timestamp_ms,
        )
        record_score(score, decision)
    except Exception as e:
        log.error("score_persist_error", symbol=snap.symbol, error=str(e))

    # ── Alert on significant score ────────────────────────────────────────
    if decision in (
        GateDecision.ALERT,
        GateDecision.FULL_AUTO,
        GateDecision.FULL_AUTO_STRONG,
    ):
        try:
            await send_signal_alert(score, decision)
        except Exception as e:
            log.error("signal_alert_error", symbol=snap.symbol, error=str(e))

    # ── Execute if FULL_AUTO or FULL_AUTO_STRONG ──────────────────────────
    if decision not in (GateDecision.FULL_AUTO, GateDecision.FULL_AUTO_STRONG):
        return

    # ── Final check: circuit breaker, no excessive positions ──────────────
    if not portfolio_state or portfolio_state.circuit_breaker:
        return
    if portfolio_state.open_position_count >= 5:
        log.debug("max_positions_reached")
        return

    # ── Build proposal ────────────────────────────────────────────────────
    instr = get_instrument(snap.symbol)
    entry = snap.tick.ask if score.direction == "LONG" else snap.tick.bid
    stop_loss = compute_stop_loss(entry, score.direction, snap.atr_5m)
    spread_pct = snap.tick.spread / snap.tick.mid if snap.tick.mid > 0 else 1.0

    proposal = ProposedOrder(
        symbol=snap.symbol,
        direction=score.direction,
        entry_price=entry,
        stop_loss=stop_loss,
        atr_5m=snap.atr_5m,
        spread_pct=spread_pct,
        hc_score=score.composite,
        regime=score.regime,
        session=score.session,
    )

    # ── Validate with risk governor ───────────────────────────────────────
    port_snap = RiskPortfolioSnapshot(
        net_equity=portfolio_state.net_equity,
        starting_equity=portfolio_state.starting_equity,
        daily_pnl=portfolio_state.daily_pnl,
        open_position_count=portfolio_state.open_position_count,
        total_basket_risk=portfolio_state.total_basket_risk,
        margin_utilisation=portfolio_state.margin_utilisation,
        day_locked=portfolio_state.day_locked,
    )

    validation = risk_governor.validate(proposal, port_snap)
    if not validation.approved:
        log.info("order_rejected", symbol=snap.symbol, reason=validation.reason)
        return

    # ── Execute order ─────────────────────────────────────────────────────
    pid = await _next_position_id()
    order = ValidatedOrder(
        position_id=pid,
        symbol=snap.symbol,
        direction=score.direction,
        lot_size=validation.lot_size,
        entry_price=entry,
        stop_loss=stop_loss,
        hc_score=score.composite,
        regime=score.regime,
        session=score.session,
    )

    # Reset hysteresis gate after entry
    gate.reset(snap.symbol)

    fill = await commander.open_position(order, snap.atr_5m, snap.tick.mid)
    if not fill or not fill.success:
        log.error(
            "fill_failed",
            symbol=snap.symbol,
            error=fill.error if fill else "Unknown error",
        )
        return

    # ── Create position state machine ─────────────────────────────────────
    sm = PositionStateMachine(
        position_id=pid,
        symbol=snap.symbol,
        direction=score.direction,
        entry=fill.fill_price,
        stop_loss=stop_loss,
        lots=fill.lots,
        fill_ts_ms=int(time.time() * 1000),
        pip_value=instr.pip_value,
        pip_size=instr.pip_size,
    )
    portfolio_state.add_position(sm)
    position_registry.add_position(sm, portfolio_state)

    # ── Persist to database ───────────────────────────────────────────────
    try:
        leverage = compute_leverage(snap.atr_5m, snap.tick.mid)
        await write_position_opened(
            position_id=pid,
            symbol=snap.symbol,
            direction=score.direction,
            entry_price=fill.fill_price,
            stop_loss=stop_loss,
            lot_size=fill.lots,
            leverage=leverage,
            hc_score=score.composite,
            regime=score.regime,
            session=score.session,
            mt5_ticket=fill.mt5_ticket,
            open_ts=int(time.time() * 1000),
        )
        # Record to trade journal
        record_opened(
            position_id=pid,
            symbol=snap.symbol,
            direction=score.direction,
            entry_price=fill.fill_price,
            lot_size=fill.lots,
            stop_loss=stop_loss,
            hc_score=score.composite,
            regime=score.regime,
        )
    except Exception as e:
        log.error("position_persist_error", position_id=pid, error=str(e))

    log.info(
        "position_opened",
        id=pid,
        symbol=snap.symbol,
        direction=score.direction,
        entry=fill.fill_price,
        lots=fill.lots,
        hc=score.composite,
        latency_ms=round(fill.latency_ms, 1),
    )


async def _next_position_id() -> int:
    """Get next sequential position ID."""
    global _pos_id_counter
    pid = _pos_id_counter
    _pos_id_counter += 1
    return pid


# ── Startup ────────────────────────────────────────────────────────────────


async def startup() -> tuple:
    """
    Initialize all components.
    Returns tuple of (pipe_client, pipe_reader, fill_handler, nuclear_controller).
    """
    global portfolio_state, nuclear_controller, position_registry
    global gate, risk_governor, commander, ledger, _pos_id_counter

    settings = get_settings()
    log.info("ghost_grid_starting", paper=settings.paper_trading)

    # ── Step 1-2: Database ──────────────────────────────────────────────
    db_conn = await get_async_connection()
    await run_migrations(db_conn)

    # ── Step 3: Crash recovery ─────────────────────────────────────────
    _pos_id_counter = await get_next_position_id()
    open_db_positions = await get_open_positions_from_db()
    if open_db_positions:
        log.warning(
            "crash_recovery_detected",
            open_positions_count=len(open_db_positions),
        )

    # ── Step 4: Portfolio state ────────────────────────────────────────
    portfolio_state = PortfolioState()
    ledger = Ledger()
    gate = ConfluenceGate()
    risk_governor = RiskGovernor()

    # ── Step 5: Named Pipe bridge (dual-pipe: ticks read / commands write)
    ticks_pipe_path = str(settings.pipe_path) + "_ticks"
    commands_pipe_path = str(settings.pipe_path) + "_commands"

    ticks_pipe = PipeClient(pipe_path=ticks_pipe_path)
    commands_pipe = PipeClient(pipe_path=commands_pipe_path)

    reader = PipeReader(ticks_pipe)
    # Dispatcher/Dispatcher-like constructor may differ across versions; prefer
    # a PipeDispatcher-compatible object. If a module level `Dispatcher` exists
    # use it, otherwise try importing PipeDispatcher directly.
    try:
        dispatcher = Dispatcher(commands_pipe)
    except Exception:
        from execution.dispatcher import PipeDispatcher

        dispatcher = PipeDispatcher(str(settings.pipe_path), pipe_client=commands_pipe)

    fill_handler = FillHandler(reader)
    writer = PipeWriter(commands_pipe)
    # Attach writer to fill_handler for legacy metrics caller
    setattr(fill_handler, "writer", writer)

    # Paper trading mode: use a simulated commander to avoid real pipe I/O
    if settings.paper_trading:
        from execution.paper import PaperExecutionCommander

        commander = PaperExecutionCommander()
    else:
        # Construct ExecutionCommander and inject dispatcher/fill_handler
        try:
            commander = ExecutionCommander()
            # Inject the dispatcher instance we created (commands_pipe-backed)
            setattr(commander, "dispatcher", dispatcher)
            setattr(commander, "fill_handler", fill_handler)
        except Exception:
            commander = ExecutionCommander()

    # Set the next id where supported
    if hasattr(commander, "set_next_id"):
        try:
            commander.set_next_id(_pos_id_counter)
        except Exception:
            pass

    # ── Step 6: Position registry ──────────────────────────────────────
    position_registry = PositionRegistry()

    # ── Step 7: Nuclear controller ─────────────────────────────────────
    nuclear_controller = NuclearController(
        state=portfolio_state,
        commander=commander,
        telegram_alerts=send_nuclear_alert,
    )

    # Backwards-compatible single `pipe` return (commands pipe)
    pipe = commands_pipe
    return pipe, reader, fill_handler, nuclear_controller, writer


# ── Background tasks ───────────────────────────────────────────────────────


async def daily_reset_task() -> None:
    """Reset daily PnL and mode at UTC midnight."""
    while True:
        now = datetime.utcnow()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        wait_s = (midnight - now).total_seconds()
        await asyncio.sleep(wait_s)

        if portfolio_state and ledger:
            # Generate end-of-day report before reset
            try:
                report = generate_daily_report(
                    starting_equity=portfolio_state.starting_equity,
                    ending_equity=portfolio_state.net_equity,
                    realized_pnl=portfolio_state.realized_pnl,
                    unrealized_pnl=portfolio_state.unrealized_pnl,
                    open_position_count=portfolio_state.open_position_count,
                    nuclear_count=portfolio_state.nuclear_count_today,
                    drift_status="OK",
                )
                log.info(
                    "daily_report_generated",
                    date=report.date_utc,
                    equity=report.summary.get("ending_equity"),
                )
                # Send report via Telegram if available
                try:
                    await _send(report.to_telegram_message())
                except Exception as e:
                    log.error("daily_report_telegram_error", error=str(e))
            except Exception as e:
                log.error("daily_report_generation_error", error=str(e))

            # Reset daily tracking
            ledger.reset_daily(portfolio_state, portfolio_state.net_equity)
            log.info("daily_reset_complete")


async def drift_check_task() -> None:
    """Check win rate drift vs backtest every hour."""
    while True:
        await asyncio.sleep(3600)
        alert = check_drift()
        if alert.drifted:
            try:
                await _send(
                    "⚠️ <b>DRIFT ALERT</b>\n"
                    "Live win rate has drifted significantly below backtest baseline.\n"
                    "Consider switching to SCALP_REDUCED or halting for review."
                )
            except Exception as e:
                log.error("drift_alert_send_error", error=str(e))


async def metrics_report_task(reader: PipeReader, writer: PipeWriter) -> None:
    """Periodically report system metrics."""
    while True:
        try:
            await asyncio.sleep(60)
            reader_metrics = reader.metrics
            writer_metrics = writer.metrics

            log.info(
                "metrics_report",
                reader_ticks=reader_metrics.ticks_dispatched,
                reader_fills=reader_metrics.fills_dispatched,
                writer_enqueued=writer_metrics.total_enqueued,
                writer_written=writer_metrics.total_written,
                positions_open=len(portfolio_state.open_positions)
                if portfolio_state
                else 0,
                nuclear_today=portfolio_state.nuclear_count_today
                if portfolio_state
                else 0,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("metrics_report_error", error=str(e))


# ── Main ───────────────────────────────────────────────────────────────────


async def wait_for_shutdown() -> None:
    """Wait for shutdown signal."""
    await _shutdown_event.wait()
    log.info("shutdown_signal_received")


async def main() -> None:
    """Production main orchestration."""
    settings = get_settings()

    # Startup sequence (steps 1-7)
    pipe, reader, fill_handler, nuke_ctrl, writer = await startup()

    # Step 5: Feed router (data pipeline)
    router = FeedRouter(reader, on_snapshot)

    # Step 5: Reconnect manager
    reconnect = ReconnectManager(pipe, reader)

    # Step 8: Watchdog OS thread (independent failsafe)
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: portfolio_state.get_frozen_snapshot() if portfolio_state else None
    )
    watchdog.start()

    # Step 9: Telegram bot
    tg_app = build_application(portfolio_state, nuclear_controller)

    # Setup graceful shutdown (add_signal_handler may not be implemented on Windows)
    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: _shutdown_event.set())
    except NotImplementedError:
        # Fallback for Windows where add_signal_handler isn't implemented
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_args: _shutdown_event.set())

    log.info(
        "ghost_grid_live",
        paper=settings.paper_trading,
        mode=settings.log_level,
    )

    # Connect to MT5 pipe (skip when running in paper trading mode)
    if not settings.paper_trading:
        try:
            await pipe.connect()
        except Exception as e:
            log.error("pipe_connect_failed", error=str(e))
            return

    # Step 10: Run all tasks concurrently
    try:
        await asyncio.gather(
            # Core pipeline
            reconnect.run(),
            reader.run(),
            writer.run(),
            fill_handler.run(),
            router.run(),
            # Nuclear guardian
            nuke_ctrl.run(),
            # Background tasks
            daily_reset_task(),
            drift_check_task(),
            metrics_report_task(reader, fill_handler.writer),
            # Telegram
            tg_app.run_polling(),
            # Shutdown signal
            wait_for_shutdown(),
        )
    finally:
        # Teardown
        log.info("shutting_down")
        watchdog.stop()
        await pipe.close()
        log.info("ghost_grid_stopped")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("interrupted_by_user")
        sys.exit(0)
    except Exception as e:
        log.error("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)

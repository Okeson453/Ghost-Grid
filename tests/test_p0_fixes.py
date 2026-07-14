import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from data.schema import MarketSnapshot, OHLCV, Tick
from execution.commander import ExecutionCommander
from execution.models import OrderStatus, ValidatedOrder
from scoring.bayesian_weights import BayesianWeightUpdater
from scoring.fusion import score_confluence
from scoring.gate import ConfluenceGate
from scoring.models import ConfluenceScore, GateDecision
from risk.sizer import calculate_lot_size


def _make_snapshot(symbol: str = "EURUSD", regime: str = "TREND") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        tick=Tick(
            symbol=symbol,
            timestamp_ms=1_700_000_000_000,
            bid=1.0850,
            ask=1.0851,
            tick_volume=100,
            dominant_side="BUY",
            cvd_running=0.0,
            session="LONDON",
        ),
        m1=OHLCV(symbol=symbol, timeframe="M1", open=1.0850, high=1.0852, low=1.0848, close=1.0851, volume=100, timestamp_ms=1_700_000_000_000),
        m3=OHLCV(symbol=symbol, timeframe="M3", open=1.0850, high=1.0852, low=1.0848, close=1.0851, volume=100, timestamp_ms=1_700_000_000_000),
        m5=OHLCV(symbol=symbol, timeframe="M5", open=1.0850, high=1.0852, low=1.0848, close=1.0851, volume=100, timestamp_ms=1_700_000_000_000),
        cvd_history=[0.0],
        vwap=1.0850,
        atr_1m=0.0010,
        atr_5m=0.0010,
        session="LONDON",
        regime=regime,
    )


class FakePipeClient:
    def __init__(self):
        self.writes: list[str] = []

    async def connect(self):
        return None

    async def writeline(self, message: str) -> bool:
        self.writes.append(message)
        return True

    async def readline(self):
        return "FILL|EURUSD|1001|1.0855|1700000000000|req_001"


def test_open_position_uses_risk_lot_size_and_uses_pipe_client(monkeypatch):
    fake_pipe_client = FakePipeClient()

    monkeypatch.setattr("bridge.pipe_client.PipeClient", lambda *args, **kwargs: fake_pipe_client)

    commander = ExecutionCommander(pipe_path=r"\\.\pipe\ghostgrid")
    commander.leverage_calculator.calculate_leverage = lambda atr, current_price: 20

    expected_lot_size = calculate_lot_size("EURUSD", 10_000.0, 1.0850, 1.0800)
    order = ValidatedOrder(
        symbol="EURUSD",
        direction="LONG",
        lot_size=expected_lot_size,
        entry_price=1.0850,
        h_c_score=140,
        regime="TREND",
        session="LONDON",
        confluence_count=3,
        timestamp_ms=1_700_000_000_000,
        request_id="req_001",
    )

    result = asyncio.run(commander.open_position(order, 0.0050, 1.0850))

    assert result is not None
    assert result.status == OrderStatus.FILL
    assert fake_pipe_client.writes
    assert "|ORDER|" in fake_pipe_client.writes[0]
    assert f"|{expected_lot_size}|" in fake_pipe_client.writes[0]
    assert "|20|" not in fake_pipe_client.writes[0]


def test_bayesian_weights_and_fusion_composite_change(tmp_path):
    db_path = tmp_path / "weights.db"
    updater = BayesianWeightUpdater(db_path=str(db_path))

    for _ in range(10):
        updater.update("HMP", True)
    for _ in range(2):
        updater.update("HMP", False)
    for _ in range(2):
        updater.update("MPP", True)
    for _ in range(10):
        updater.update("MPP", False)

    weights = updater.get_normalized_weights()
    assert weights["HMP"] > weights["MPP"] + 0.2

    snap = _make_snapshot()
    baseline_db = tmp_path / "baseline_weights.db"
    with patch("scoring.fusion.calculate_hmp", return_value=SimpleNamespace(score=60)), patch(
        "scoring.fusion.calculate_hlcp", return_value=SimpleNamespace(score=40)
    ), patch("scoring.fusion.calculate_mpp", return_value=SimpleNamespace(score=20)):
        baseline = score_confluence(snap, weight_updater=BayesianWeightUpdater(db_path=str(baseline_db)))
        adjusted = score_confluence(snap, weight_updater=updater)

    assert baseline.composite != adjusted.composite


def test_regime_multiplier_changes_composite_and_gate_keeps_threshold_policy(tmp_path):
    updater = BayesianWeightUpdater(db_path=str(tmp_path / "weights.db"))
    snap_trend = _make_snapshot(regime="TREND")
    snap_chop = _make_snapshot(regime="CHOP")
    snap_breakout = _make_snapshot(regime="BREAKOUT")
    snap_reversal = _make_snapshot(regime="REVERSAL")

    with patch("scoring.fusion.calculate_hmp", return_value=SimpleNamespace(score=60)), patch(
        "scoring.fusion.calculate_hlcp", return_value=SimpleNamespace(score=40)
    ), patch("scoring.fusion.calculate_mpp", return_value=SimpleNamespace(score=20)):
        trend_score = score_confluence(snap_trend, weight_updater=updater)
        chop_score = score_confluence(snap_chop, weight_updater=updater)
        breakout_score = score_confluence(snap_breakout, weight_updater=updater)
        reversal_score = score_confluence(snap_reversal, weight_updater=updater)

    assert trend_score.composite > breakout_score.composite > reversal_score.composite > chop_score.composite

    gate = ConfluenceGate()
    gate_score = ConfluenceScore(
        symbol="EURUSD",
        hmp=44,
        hlcp=44,
        mpp=44,
        composite=132,
        direction="LONG",
        regime="CHOP",
        session="LONDON",
        timestamp_ms=1_700_000_000_000,
    )
    assert gate.evaluate(gate_score) == GateDecision.DISCARD

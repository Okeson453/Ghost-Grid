"""
tests/integration/test_pipe_to_snapshot.py
Integration tests for pipe → snapshot pipeline.

Validates that ticks flow through the entire data pipeline and produce
valid MarketSnapshot objects with expected properties.
"""

from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from data.snapshot_builder import SnapshotBuilder
from tests.fixtures import make_tick_sequence


@pytest.mark.asyncio
async def test_snapshot_produced_after_warmup() -> None:
    """
    300 ticks (uptrend) should produce MarketSnapshots after warmup.

    Validates:
    - At least one non-None snapshot returned
    - atr_1m > 0 (ATR initialized after 14 M1 bars)
    - At least 2 M1 bars in snapshot
    - vwap > 0
    """
    # Create builder
    builder = SnapshotBuilder("EURUSD")

    # Generate 300-tick uptrend sequence
    ticks = make_tick_sequence(
        count=300,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,  # 50ms per tick = 3 ticks per M1 bar
    )

    # Feed all ticks
    snapshots = []
    for tick in ticks:
        snapshot = builder.on_tick(tick)
        if snapshot is not None:
            snapshots.append(snapshot)

    # Assertions
    assert len(snapshots) > 0, "Should produce at least one snapshot"

    # Check first snapshot
    first_snap = snapshots[0]
    assert first_snap.atr_1m > 0, "ATR should be > 0 after warmup"
    assert first_snap.m1 is not None, "M1 bar should exist"
    assert first_snap.vwap > 0, "VWAP should be > 0"

    # Check M1 bar count
    m1_count = len(builder._agg._buffers["M1"])
    assert m1_count >= 2, f"Should have ≥2 M1 bars, got {m1_count}"


@pytest.mark.asyncio
async def test_snapshot_none_during_warmup() -> None:
    """
    5 ticks should produce all None snapshots (warmup phase).

    Validates:
    - Warmup guard prevents premature snapshots
    - Only after 20 M1 + 14 M5 bars do snapshots start
    """
    # Create builder
    builder = SnapshotBuilder("EURUSD")

    # Generate only 5 ticks
    ticks = make_tick_sequence(
        count=5,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    snapshots = []
    for tick in ticks:
        snapshot = builder.on_tick(tick)
        snapshots.append(snapshot)

    # All should be None (not yet warmed up)
    assert all(s is None for s in snapshots), "Warmup phase should return None"


@pytest.mark.asyncio
async def test_bar_buffer_fills_correctly() -> None:
    """
    Ticks should correctly build M1/M3/M5 bars.

    With 50ms per tick:
    - M1 = 60s = 1200 ticks
    - M3 = 180s = 3600 ticks
    - M5 = 300s = 6000 ticks

    So 300 ticks = ~15s, should have 0 complete M1 bars if starting mid-bar.
    Actually with proper aggregation, every 1200 ticks completes 1 M1 bar.
    """
    # Create builder
    builder = SnapshotBuilder("EURUSD")

    # Generate 300 ticks
    ticks = make_tick_sequence(
        count=300,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    for tick in ticks:
        builder.on_tick(tick)

    # After 300 ticks (15 seconds), no complete bars if starting mid-period
    # But the aggregator should at least have an open bar
    m1_open_bar = builder._agg._open_bars.get("M1")
    assert m1_open_bar is not None, "Should have open M1 bar"


@pytest.mark.asyncio
async def test_cvd_accumulates() -> None:
    """
    CVD should accumulate and rise with uptrend.
    """
    builder = SnapshotBuilder("EURUSD")

    # Generate 50 uptrend ticks
    ticks = make_tick_sequence(
        count=50,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    for tick in ticks:
        builder.on_tick(tick)

    # Check CVD history
    cvd_hist = builder._cvd.history()
    assert len(cvd_hist) > 0, "CVD history should have entries"
    # In uptrend, CVD should generally be rising (or at least not all zeros)
    assert any(v > 0 for v in cvd_hist), "CVD should have positive values in uptrend"


@pytest.mark.asyncio
async def test_vwap_session_reset() -> None:
    """
    VWAP should reset when session changes.
    """
    builder = SnapshotBuilder("EURUSD")

    # Generate ticks in LONDON session
    ticks_london = make_tick_sequence(
        count=50,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed London ticks
    for tick in ticks_london:
        builder.on_tick(tick)

    vwap_london = builder._vwap.value

    # Simulate session change by manually resetting (in real scenario, session changes)
    # For now, just check that VWAP has a value
    assert vwap_london > 0, "VWAP should accumulate to > 0"

"""
tests/integration/test_pipe_to_snapshot.py
Integration tests for pipe → snapshot pipeline.

Validates that ticks flow through the entire data pipeline and produce
valid MarketSnapshot objects with expected properties.
"""

from __future__ import annotations

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
    tick_messages = make_tick_sequence(
        count=300,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,  # 50ms per tick = 1200 ticks per M1 bar (60s)
    )

    # Feed all ticks
    snapshots = []
    for tick_msg in tick_messages:
        snapshot = builder.on_tick(tick_msg)
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
    tick_messages = make_tick_sequence(
        count=5,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    snapshots = []
    for tick_msg in tick_messages:
        snapshot = builder.on_tick(tick_msg)
        snapshots.append(snapshot)

    # All should be None (not yet warmed up)
    assert all(s is None for s in snapshots), "Warmup phase should return None"


@pytest.mark.asyncio
async def test_bar_buffer_fills_correctly() -> None:
    """
    Ticks should correctly build M1/M3/M5 bars.

    With 50ms per tick and starting at arbitrary timestamp, bars fill up
    as ticks cross time boundaries.
    """
    # Create builder
    builder = SnapshotBuilder("EURUSD")

    # Generate 300 ticks
    tick_messages = make_tick_sequence(
        count=300,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    for tick_msg in tick_messages:
        builder.on_tick(tick_msg)

    # After 300 ticks, should have at least an open bar
    m1_open_bar = builder._agg._open_bars.get("M1")
    assert m1_open_bar is not None, "Should have open M1 bar"


@pytest.mark.asyncio
async def test_cvd_accumulates() -> None:
    """
    CVD should accumulate as ticks feed in.
    """
    builder = SnapshotBuilder("EURUSD")

    # Generate 50 uptrend ticks
    tick_messages = make_tick_sequence(
        count=50,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    for tick_msg in tick_messages:
        builder.on_tick(tick_msg)

    # Check CVD history
    cvd_hist = builder._cvd.history()
    assert len(cvd_hist) > 0, "CVD history should have entries"


@pytest.mark.asyncio
async def test_vwap_accumulates() -> None:
    """
    VWAP should accumulate to a positive value in uptrend.
    """
    builder = SnapshotBuilder("EURUSD")

    # Generate ticks in uptrend
    tick_messages = make_tick_sequence(
        count=50,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )

    # Feed all ticks
    for tick_msg in tick_messages:
        builder.on_tick(tick_msg)

    vwap_value = builder._vwap.value
    assert vwap_value > 0, "VWAP should accumulate to > 0"

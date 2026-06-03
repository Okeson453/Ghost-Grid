"""
tests/scoring/hmp/test_swing.py
Unit tests for swing high/low detection.
"""

import pytest
from data.schema import OHLCV
from scoring.hmp.swing import (
    detect_swing_highs,
    detect_swing_lows,
    get_last_swing_high,
    get_last_swing_low,
)


@pytest.fixture
def sample_bars():
    """Create a sample OHLCV bar sequence."""
    return [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0840, 1.0850, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0850, 1.0870, 1.0845, 1.0865, 1200.0, 2000),
        OHLCV("EURUSD", "M5", 1.0865, 1.0880, 1.0860, 1.0875, 1100.0, 3000),
        OHLCV("EURUSD", "M5", 1.0875, 1.0900, 1.0870, 1.0895, 1300.0, 4000),
        OHLCV("EURUSD", "M5", 1.0895, 1.0910, 1.0890, 1.0905, 1150.0, 5000),
        OHLCV("EURUSD", "M5", 1.0905, 1.0920, 1.0900, 1.0915, 1400.0, 6000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0910, 1.0920, 1250.0, 7000),
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0918, 1100.0, 8000),
        OHLCV("EURUSD", "M5", 1.0918, 1.0935, 1.0912, 1.0930, 1350.0, 9000),
        OHLCV("EURUSD", "M5", 1.0930, 1.0945, 1.0925, 1.0940, 1200.0, 10000),
    ]


def test_detect_swing_highs_basic(sample_bars):
    """Test basic swing high detection."""
    highs = detect_swing_highs(sample_bars, window=2, lookback=20)
    assert len(highs) > 0
    assert all(sh.swing_type == "HIGH" for sh in highs)
    assert all(sh.price > 0 for sh in highs)


def test_detect_swing_lows_basic(sample_bars):
    """Test basic swing low detection."""
    lows = detect_swing_lows(sample_bars, window=2, lookback=20)
    assert len(lows) > 0
    assert all(sl.swing_type == "LOW" for sl in lows)
    assert all(sl.price > 0 for sl in lows)


def test_swing_high_price_correctness(sample_bars):
    """Verify swing high prices are actually local highs."""
    highs = detect_swing_highs(sample_bars, window=1, lookback=20)
    for swing in highs:
        idx = len(sample_bars) + swing.bar_index
        if 0 < idx < len(sample_bars) - 1:
            assert sample_bars[idx].high >= sample_bars[idx - 1].high
            assert sample_bars[idx].high >= sample_bars[idx + 1].high


def test_get_last_swing_high(sample_bars):
    """Test retrieving the most recent swing high."""
    last_high = get_last_swing_high(sample_bars)
    assert last_high is not None
    assert last_high.swing_type == "HIGH"


def test_get_last_swing_low(sample_bars):
    """Test retrieving the most recent swing low."""
    last_low = get_last_swing_low(sample_bars)
    assert last_low is not None
    assert last_low.swing_type == "LOW"


def test_insufficient_bars():
    """Test behavior with insufficient bars."""
    short_bars = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0840, 1.0850, 1000.0, 1000),
    ]
    highs = detect_swing_highs(short_bars, window=2)
    lows = detect_swing_lows(short_bars, window=2)
    assert len(highs) == 0
    assert len(lows) == 0


def test_window_parameter(sample_bars):
    """Test different window sizes."""
    highs_w1 = detect_swing_highs(sample_bars, window=1, lookback=20)
    highs_w2 = detect_swing_highs(sample_bars, window=2, lookback=20)
    # Larger window should find fewer swing points (stricter criteria)
    assert len(highs_w2) <= len(highs_w1)


def test_lookback_parameter(sample_bars):
    """Test lookback parameter limits search range."""
    highs_all = detect_swing_highs(sample_bars, window=2, lookback=20)
    highs_recent = detect_swing_highs(sample_bars, window=2, lookback=5)
    # Recent lookback should find same or fewer points
    assert len(highs_recent) <= len(highs_all)


def test_swing_timestamp_preservation(sample_bars):
    """Verify swing points preserve original timestamp."""
    highs = detect_swing_highs(sample_bars, window=2, lookback=20)
    for swing in highs:
        idx = len(sample_bars) + swing.bar_index
        if 0 <= idx < len(sample_bars):
            assert swing.timestamp_ms == sample_bars[idx].timestamp_ms


def test_swing_bar_index_validity(sample_bars):
    """Verify bar_index is valid and negative (from end)."""
    highs = detect_swing_highs(sample_bars, window=2, lookback=20)
    for swing in highs:
        assert swing.bar_index < 0, "bar_index should be negative (from end)"
        actual_idx = len(sample_bars) + swing.bar_index
        assert 0 <= actual_idx < len(sample_bars), "bar_index should map to valid bar"


def test_most_recent_first_ordering(sample_bars):
    """Verify results are ordered most recent first."""
    highs = detect_swing_highs(sample_bars, window=2, lookback=20)
    if len(highs) > 1:
        # Most recent should have a bar_index closer to 0 (more negative = older)
        for i in range(len(highs) - 1):
            assert highs[i].bar_index > highs[i + 1].bar_index

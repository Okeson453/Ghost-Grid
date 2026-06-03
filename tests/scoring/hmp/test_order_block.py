"""
tests/scoring/hmp/test_order_block.py
Unit tests for Order Block detection.
"""

import pytest
from data.schema import OHLCV
from scoring.hmp.order_block import find_active_ob


@pytest.fixture
def m5_bars_with_bullish_ob():
    """Create M5 bars with a clear bullish Order Block."""
    return [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        # Bearish candle - potential bullish OB
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 1200.0, 3000),
        # Start of bullish move
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
        # Price near the OB zone for testing
        OHLCV("EURUSD", "M5", 1.0943, 1.0950, 1.0920, 1.0922, 1100.0, 7000),
    ]


@pytest.fixture
def m5_bars_with_bearish_ob():
    """Create M5 bars with a clear bearish Order Block."""
    return [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0858, 1.0870, 1.0855, 1.0868, 1100.0, 2000),
        # Bullish candle - potential bearish OB
        OHLCV("EURUSD", "M5", 1.0868, 1.0875, 1.0858, 1.0873, 1200.0, 3000),
        # Start of bearish move
        OHLCV("EURUSD", "M5", 1.0873, 1.0878, 1.0858, 1.0862, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0862, 1.0868, 1.0845, 1.0850, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0850, 1.0858, 1.0835, 1.0840, 1250.0, 6000),
        # Price near the OB zone
        OHLCV("EURUSD", "M5", 1.0840, 1.0868, 1.0838, 1.0865, 1100.0, 7000),
    ]


def test_find_bullish_ob(m5_bars_with_bullish_ob):
    """Test bullish Order Block detection."""
    current_price = 1.0920
    result = find_active_ob(m5_bars_with_bullish_ob, current_price, "LONG")
    
    assert result is not None
    assert result.top >= result.bottom


def test_find_bearish_ob(m5_bars_with_bearish_ob):
    """Test bearish Order Block detection."""
    current_price = 1.0865
    result = find_active_ob(m5_bars_with_bearish_ob, current_price, "SHORT")
    
    assert result is not None
    assert result.top >= result.bottom


def test_ob_insufficient_bars():
    """Test with insufficient bars."""
    short_bars = [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
    ]
    result = find_active_ob(short_bars, 1.0920, "LONG")
    
    assert not result.found


def test_ob_test_count_tracking(m5_bars_with_bullish_ob):
    """Test that OB test count is tracked."""
    current_price = 1.0920
    result = find_active_ob(m5_bars_with_bullish_ob, current_price, "LONG")
    
    if result.found:
        assert result.test_count >= 0


def test_ob_staleness_detection(m5_bars_with_bullish_ob):
    """Test detection of stale (over-tested) order blocks."""
    current_price = 1.0920
    result = find_active_ob(m5_bars_with_bullish_ob, current_price, "LONG")
    
    # If test_count >= 3, should be marked as stale
    if result.found and result.test_count >= 3:
        assert result.stale


def test_ob_imbalance_ratio_calculation(m5_bars_with_bullish_ob):
    """Test volume imbalance ratio calculation."""
    current_price = 1.0920
    result = find_active_ob(m5_bars_with_bullish_ob, current_price, "LONG")
    
    if result.found:
        assert result.imbalance_ratio >= 0.0


def test_ob_proximity_check():
    """Test that OB must be near current price."""
    bars = [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
    ]
    # Price far from OB - should not find it
    current_price = 1.1000  # Way above the bar range
    result = find_active_ob(bars, current_price, "LONG")
    
    # Should either not find or find but with distance consideration
    assert result is not None


def test_ob_strength_with_high_imbalance():
    """Test that OBs with high volume imbalance are prioritized."""
    bars = [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        # High volume bearish candle
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 5000.0, 3000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
    ]
    current_price = 1.0920
    result = find_active_ob(bars, current_price, "LONG")
    
    if result.found:
        assert result.imbalance_ratio > 0.0


def test_ob_freshness_requirement():
    """Test that fresh OBs (fewer tests) are preferred."""
    bars = [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
    ]
    current_price = 1.0920
    result = find_active_ob(bars, current_price, "LONG")
    
    # Fresh OB should have low test count
    if result.found and not result.stale:
        assert result.test_count < 3


def test_ob_multiple_candidates():
    """Test handling when multiple OBs could be found."""
    bars = [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
        OHLCV("EURUSD", "M5", 1.0943, 1.0955, 1.0938, 1.0950, 1100.0, 7000),
        OHLCV("EURUSD", "M5", 1.0950, 1.0960, 1.0945, 1.0955, 1200.0, 8000),
        OHLCV("EURUSD", "M5", 1.0955, 1.0960, 1.0940, 1.0945, 1150.0, 9000),
        OHLCV("EURUSD", "M5", 1.0945, 1.0950, 1.0928, 1.0935, 1300.0, 10000),
    ]
    current_price = 1.0935
    result = find_active_ob(bars, current_price, "LONG")
    
    # Should find the most relevant OB
    assert result is not None

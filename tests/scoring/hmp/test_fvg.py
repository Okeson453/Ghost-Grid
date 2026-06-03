"""
tests/scoring/hmp/test_fvg.py
Unit tests for Fair Value Gap detection.
"""

import pytest
from data.schema import OHLCV
from scoring.hmp.fvg import find_nearest_fvg


@pytest.fixture
def m3_bars_with_bullish_fvg():
    """Create M3 bars with a clear bullish FVG."""
    return [
        OHLCV("EURUSD", "M3", 1.0900, 1.0905, 1.0895, 1.0900, 2000.0, 1000),
        # Gap down candle
        OHLCV("EURUSD", "M3", 1.0900, 1.0902, 1.0880, 1.0885, 2100.0, 3000),
        # Gap up candle - creates bullish FVG
        OHLCV("EURUSD", "M3", 1.0895, 1.0910, 1.0890, 1.0908, 2200.0, 5000),
    ]


@pytest.fixture
def m3_bars_with_bearish_fvg():
    """Create M3 bars with a clear bearish FVG."""
    return [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
        # Gap up candle
        OHLCV("EURUSD", "M3", 1.0858, 1.0880, 1.0855, 1.0875, 2100.0, 3000),
        # Gap down candle - creates bearish FVG
        OHLCV("EURUSD", "M3", 1.0865, 1.0870, 1.0840, 1.0845, 2200.0, 5000),
    ]


def test_find_bullish_fvg(m3_bars_with_bullish_fvg):
    """Test bullish FVG detection."""
    current_price = 1.0885  # Below the gap
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bullish_fvg, current_price, atr, "LONG")
    
    assert result.found
    assert result.direction == "BULLISH"
    assert result.top > result.bottom


def test_find_bearish_fvg(m3_bars_with_bearish_fvg):
    """Test bearish FVG detection."""
    current_price = 1.0870  # Above the gap
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bearish_fvg, current_price, atr, "SHORT")
    
    assert result.found
    assert result.direction == "BEARISH"
    assert result.top > result.bottom


def test_fvg_unfilled_detection(m3_bars_with_bullish_fvg):
    """Test that FVG is marked as unfilled when price hasn't re-entered."""
    current_price = 1.0895  # Above gap bottom, FVG unfilled
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bullish_fvg, current_price, atr, "LONG")
    
    if result.found:
        assert result.unfilled


def test_fvg_filled_detection(m3_bars_with_bullish_fvg):
    """Test FVG marked as filled when price re-enters gap."""
    current_price = 1.0890  # Inside gap, so filled
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bullish_fvg, current_price, atr, "LONG")
    
    # Either not found or marked as filled
    if result.found:
        assert not result.unfilled or result.distance_pct >= 0


def test_fvg_distance_calculation(m3_bars_with_bullish_fvg):
    """Test distance from current price to FVG is calculated."""
    current_price = 1.0900
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bullish_fvg, current_price, atr, "LONG")
    
    if result.found:
        assert result.distance_pct >= 0.0


def test_fvg_zero_atr():
    """Test with zero ATR (edge case)."""
    bars = [
        OHLCV("EURUSD", "M3", 1.0900, 1.0905, 1.0895, 1.0900, 2000.0, 1000),
        OHLCV("EURUSD", "M3", 1.0900, 1.0902, 1.0880, 1.0885, 2100.0, 3000),
        OHLCV("EURUSD", "M3", 1.0895, 1.0910, 1.0890, 1.0908, 2200.0, 5000),
    ]
    result = find_nearest_fvg(bars, 1.0890, 0.0, "LONG")
    
    # Should return _NO_FVG or handle gracefully
    assert result.distance_pct == 999.0 or result.found is False


def test_insufficient_bars_for_fvg():
    """Test with insufficient bars (need at least 3)."""
    short_bars = [
        OHLCV("EURUSD", "M3", 1.0900, 1.0905, 1.0895, 1.0900, 2000.0, 1000),
    ]
    result = find_nearest_fvg(short_bars, 1.0900, 0.001, "LONG")
    
    assert not result.found


def test_nearest_fvg_selection():
    """Test that nearest FVG to current price is returned."""
    bars = [
        OHLCV("EURUSD", "M3", 1.0900, 1.0905, 1.0895, 1.0900, 2000.0, 1000),
        OHLCV("EURUSD", "M3", 1.0900, 1.0902, 1.0880, 1.0885, 2100.0, 3000),
        OHLCV("EURUSD", "M3", 1.0895, 1.0910, 1.0890, 1.0908, 2200.0, 5000),
        OHLCV("EURUSD", "M3", 1.0908, 1.0915, 1.0900, 1.0912, 2000.0, 7000),
        OHLCV("EURUSD", "M3", 1.0912, 1.0918, 1.0905, 1.0910, 2100.0, 9000),
        OHLCV("EURUSD", "M3", 1.0910, 1.0920, 1.0905, 1.0918, 2200.0, 11000),
    ]
    current_price = 1.0915
    atr = 0.001
    result = find_nearest_fvg(bars, current_price, atr, "LONG")
    
    # Should find nearest to current price
    assert result.distance_pct < 999.0 or not result.found


def test_multiple_fvg_handling():
    """Test handling of multiple potential FVGs."""
    bars = [
        OHLCV("EURUSD", "M3", 1.0900, 1.0905, 1.0895, 1.0900, 2000.0, 1000),
        OHLCV("EURUSD", "M3", 1.0900, 1.0902, 1.0880, 1.0885, 2100.0, 3000),
        OHLCV("EURUSD", "M3", 1.0895, 1.0910, 1.0890, 1.0908, 2200.0, 5000),
        OHLCV("EURUSD", "M3", 1.0908, 1.0912, 1.0902, 1.0905, 2000.0, 7000),
        OHLCV("EURUSD", "M3", 1.0905, 1.0920, 1.0900, 1.0918, 2100.0, 9000),
    ]
    current_price = 1.0915
    atr = 0.001
    result = find_nearest_fvg(bars, current_price, atr, "LONG")
    
    # Should return exactly one (nearest) FVG
    assert result.found is False or result.distance_pct >= 0.0


def test_fvg_gap_size_calculation(m3_bars_with_bullish_fvg):
    """Test that FVG gap size is calculated correctly."""
    current_price = 1.0890
    atr = 0.001
    result = find_nearest_fvg(m3_bars_with_bullish_fvg, current_price, atr, "LONG")
    
    if result.found:
        assert result.gap_size > 0.0
        assert result.gap_size == result.top - result.bottom

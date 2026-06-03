"""
tests/scoring/hmp/test_bos.py
Unit tests for Break of Structure detection.
"""

import pytest
from data.schema import OHLCV
from scoring.hmp.bos import detect_bos


@pytest.fixture
def m5_bars_with_bos_long():
    """Create M5 bars with a clear LONG BOS setup."""
    return [
        OHLCV("EURUSD", "M5", 1.0850, 1.0855, 1.0845, 1.0850, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0848, 1.0858, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0858, 1.0865, 1.0852, 1.0860, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0860, 1.0870, 1.0858, 1.0862, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0862, 1.0872, 1.0860, 1.0870, 1300.0, 5000),
        # Recent swing high at 1.0872
        OHLCV("EURUSD", "M5", 1.0870, 1.0875, 1.0865, 1.0868, 1100.0, 6000),
        OHLCV("EURUSD", "M5", 1.0868, 1.0871, 1.0862, 1.0865, 1000.0, 7000),
        # Break above 1.0872 swing high - BOS LONG confirmed
        OHLCV("EURUSD", "M5", 1.0865, 1.0880, 1.0864, 1.0878, 1400.0, 8000),
    ]


@pytest.fixture
def m5_bars_with_bos_short():
    """Create M5 bars with a clear SHORT BOS setup."""
    return [
        OHLCV("EURUSD", "M5", 1.0900, 1.0910, 1.0895, 1.0905, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0905, 1.0915, 1.0900, 1.0912, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0912, 1.0920, 1.0908, 1.0918, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0918, 1.0925, 1.0910, 1.0915, 1150.0, 4000),
        # Recent swing low at 1.0910
        OHLCV("EURUSD", "M5", 1.0915, 1.0920, 1.0908, 1.0912, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0912, 1.0915, 1.0905, 1.0910, 1100.0, 6000),
        # Break below 1.0905 swing low - BOS SHORT confirmed
        OHLCV("EURUSD", "M5", 1.0910, 1.0912, 1.0900, 1.0902, 1400.0, 7000),
    ]


@pytest.fixture
def m3_bars_confirming():
    """M3 bars that confirm a BOS signal."""
    return [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
        OHLCV("EURUSD", "M3", 1.0858, 1.0870, 1.0856, 1.0868, 2100.0, 3000),
        OHLCV("EURUSD", "M3", 1.0868, 1.0875, 1.0864, 1.0872, 2200.0, 5000),
        OHLCV("EURUSD", "M3", 1.0872, 1.0885, 1.0870, 1.0880, 2300.0, 8000),
    ]


def test_bos_long_high_momentum(m5_bars_with_bos_long, m3_bars_confirming):
    """Test LONG BOS with high momentum."""
    atr = 0.001  # Small ATR for strong momentum
    result = detect_bos(m5_bars_with_bos_long, m3_bars_confirming, "LONG", atr)
    
    assert result.confirmed
    assert result.momentum > 0.0
    assert result.swing_level > 0


def test_bos_short_detection(m5_bars_with_bos_short, m3_bars_confirming):
    """Test SHORT BOS detection."""
    atr = 0.001
    result = detect_bos(m5_bars_with_bos_short, m3_bars_confirming, "SHORT", atr)
    
    assert result is not None
    assert result.swing_level > 0


def test_bos_zero_atr():
    """Test with zero ATR (edge case)."""
    bars = [OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0840, 1.0855, 1000.0, 1000)]
    result = detect_bos(bars, bars, "LONG", 0.0)
    
    assert not result.confirmed
    assert result.momentum == 0.0


def test_bos_insufficient_bars():
    """Test with insufficient bars."""
    short_bars = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0840, 1.0855, 1000.0, 1000),
    ]
    result = detect_bos(short_bars, short_bars, "LONG", 0.001)
    
    assert not result.confirmed


def test_bos_mtf_alignment_check(m5_bars_with_bos_long, m3_bars_confirming):
    """Test multi-timeframe alignment verification."""
    atr = 0.001
    result = detect_bos(m5_bars_with_bos_long, m3_bars_confirming, "LONG", atr)
    
    # If BOS is confirmed, mtf_aligned should be boolean
    assert isinstance(result.mtf_aligned, bool)


def test_bos_momentum_calculation(m5_bars_with_bos_long, m3_bars_confirming):
    """Test momentum is calculated as |close - swing| / ATR."""
    atr = 0.001
    result = detect_bos(m5_bars_with_bos_long, m3_bars_confirming, "LONG", atr)
    
    if result.confirmed and atr > 0:
        # Momentum should be positive and reasonable
        assert result.momentum >= 0.0
        assert result.momentum < 100.0  # Sanity check


def test_bos_score_contribution_high_momentum(m5_bars_with_bos_long, m3_bars_confirming):
    """Test score contribution property for high momentum."""
    atr = 0.001
    result = detect_bos(m5_bars_with_bos_long, m3_bars_confirming, "LONG", atr)
    
    if result.confirmed and result.momentum > 0.70:
        contribution = result.score_contribution
        assert contribution >= 10  # At least base score


def test_bos_score_contribution_not_confirmed():
    """Test score contribution when BOS not confirmed."""
    bars = [OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0840, 1.0855, 1000.0, 1000)]
    result = detect_bos(bars, bars, "LONG", 0.001)
    
    assert result.score_contribution == 0

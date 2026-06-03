"""
tests/positions/test_weakness.py
Unit tests for positions/weakness.py
"""

import pytest
from positions.weakness import detect_weakness, WeaknessSignal


class MockOHLCV:
    """Mock OHLCV bar for testing."""

    def __init__(self, open_, close, high, low, volume):
        self.open = open_
        self.close = close
        self.high = high
        self.low = low
        self.volume = volume

    @property
    def is_bullish(self):
        return self.close > self.open

    @property
    def is_bearish(self):
        return self.close < self.open


class TestDetectWeakness:
    """Test suite for detect_weakness."""

    def test_insufficient_bars(self):
        """Test with fewer than 6 bars."""
        bars = [MockOHLCV(1.0, 1.1, 1.2, 0.9, 100) for _ in range(5)]
        signal = detect_weakness(bars, "LONG")
        assert not signal.all_three

    def test_no_weakness(self):
        """Test with no weakness signals."""
        bars = [
            MockOHLCV(1.0, 1.01, 1.02, 0.99, 100),
            MockOHLCV(1.01, 1.02, 1.03, 1.0, 100),
            MockOHLCV(1.02, 1.03, 1.04, 1.01, 100),
            MockOHLCV(1.03, 1.04, 1.05, 1.02, 100),
            MockOHLCV(1.04, 1.05, 1.06, 1.03, 100),
            MockOHLCV(1.05, 1.06, 1.07, 1.04, 100),
        ]
        signal = detect_weakness(bars, "LONG")
        assert not signal.all_three

    def test_rsi_extreme_long(self):
        """Test RSI extreme for LONG position."""
        # Create bars with big up moves to generate high RSI
        bars = [
            MockOHLCV(1.0 + i * 0.01, 1.01 + i * 0.01, 1.02 + i * 0.01, 0.99 + i * 0.01, 100)
            for i in range(6)
        ]
        signal = detect_weakness(bars, "LONG")
        # High RSI should be detected
        assert signal.rsi_value > 50

    def test_volume_cliff(self):
        """Test volume cliff detection."""
        bars = [
            MockOHLCV(1.0, 1.01, 1.02, 0.99, 1000),
            MockOHLCV(1.01, 1.02, 1.03, 1.0, 1000),
            MockOHLCV(1.02, 1.03, 1.04, 1.01, 1000),
            MockOHLCV(1.03, 1.04, 1.05, 1.02, 1000),
            MockOHLCV(1.04, 1.05, 1.06, 1.03, 1000),
            MockOHLCV(1.05, 1.06, 1.07, 1.04, 50),  # Volume cliff
        ]
        signal = detect_weakness(bars, "LONG")
        assert signal.vol_cliff

    def test_engulfing_long(self):
        """Test bearish engulfing for LONG."""
        bars = [
            MockOHLCV(1.0, 1.01, 1.02, 0.99, 100),
            MockOHLCV(1.01, 1.02, 1.03, 1.0, 100),
            MockOHLCV(1.02, 1.03, 1.04, 1.01, 100),
            MockOHLCV(1.03, 1.04, 1.05, 1.02, 100),
            MockOHLCV(1.04, 1.05, 1.06, 1.03, 100),
            MockOHLCV(1.06, 1.04, 1.07, 1.04, 100),  # Bearish engulf
        ]
        signal = detect_weakness(bars, "LONG")
        assert signal.engulfing

    def test_engulfing_short(self):
        """Test bullish engulfing for SHORT."""
        bars = [
            MockOHLCV(1.06, 1.05, 1.07, 1.04, 100),
            MockOHLCV(1.05, 1.04, 1.06, 1.03, 100),
            MockOHLCV(1.04, 1.03, 1.05, 1.02, 100),
            MockOHLCV(1.03, 1.02, 1.04, 1.01, 100),
            MockOHLCV(1.02, 1.01, 1.03, 1.0, 100),
            MockOHLCV(1.01, 1.03, 1.04, 1.0, 100),  # Bullish engulf
        ]
        signal = detect_weakness(bars, "SHORT")
        assert signal.engulfing

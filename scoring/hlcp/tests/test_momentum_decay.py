"""
tests/scoring/hlcp/test_momentum_decay.py
Unit tests for momentum exhaustion detection (0-15 pts).
"""

import pytest
from scoring.hlcp.momentum_decay import detect_momentum_decay, score_momentum_decay
from tests.fixtures.sample_ohlcv import make_bar, make_bullish_trend


class TestMomentumDecayDetection:
    """Tests for detect_momentum_decay() function."""

    def test_insufficient_bars_returns_neutral(self):
        """< 10 bars → returns neutral signal (no exhaustion)."""
        bars = [make_bar(close=1.08000 + i * 0.00010) for i in range(5)]
        result = detect_momentum_decay(bars, "LONG")
        assert result.rsi_extreme is False
        assert result.volume_decay is False
        assert result.all_two is False

    def test_long_momentum_rsi_extreme_high(self):
        """LONG: RSI(7) > 72 → rsi_extreme = True."""
        # Create strong uptrend (high RSI)
        bars = make_bullish_trend(count=20, increment=0.00050)
        result = detect_momentum_decay(bars, "LONG")
        assert result.rsi_extreme is True
        assert result.rsi_value > 72

    def test_short_momentum_rsi_extreme_low(self):
        """SHORT: RSI(7) < 28 → rsi_extreme = True."""
        # Create strong downtrend (low RSI)
        bars = [make_bar(close=1.08500 - i * 0.00050) for i in range(20)]
        result = detect_momentum_decay(bars, "SHORT")
        assert result.rsi_extreme is True
        assert result.rsi_value < 28

    def test_volume_decay_three_consecutive_bars(self):
        """Volume declining over 3 bars → volume_decay = True."""
        bars = [
            make_bar(volume=1_000_000),
            make_bar(volume=900_000),
            make_bar(volume=800_000),
            make_bar(volume=700_000),  # 3 consecutive declines
        ]
        # Pad to 10 bars
        bars = [make_bar(volume=1_000_000)] * 6 + bars

        result = detect_momentum_decay(bars, "LONG")
        assert result.volume_decay is True

    def test_volume_not_decaying(self):
        """Volume increasing → volume_decay = False."""
        bars = [
            make_bar(volume=700_000),
            make_bar(volume=800_000),
            make_bar(volume=900_000),
            make_bar(volume=1_000_000),
        ]
        bars = [make_bar(volume=1_000_000)] * 6 + bars

        result = detect_momentum_decay(bars, "LONG")
        assert result.volume_decay is False

    def test_both_signals_present_long(self):
        """RSI > 72 AND volume declining → all_two = True (LONG exhaustion)."""
        bars = make_bullish_trend(count=20, increment=0.00050)
        # Add declining volume to last 3 bars
        bars = list(bars[:-3]) + [
            make_bar(close=bars[-3].close, volume=1_000_000),
            make_bar(close=bars[-2].close, volume=900_000),
            make_bar(close=bars[-1].close, volume=800_000),
        ]

        result = detect_momentum_decay(bars, "LONG")
        assert result.rsi_extreme is True
        assert result.volume_decay is True
        assert result.all_two is True

    def test_both_signals_present_short(self):
        """RSI < 28 AND volume declining → all_two = True (SHORT exhaustion)."""
        bars = [make_bar(close=1.08500 - i * 0.00050) for i in range(20)]
        # Add declining volume
        bars = list(bars[:-3]) + [
            make_bar(close=bars[-3].close, volume=1_000_000),
            make_bar(close=bars[-2].close, volume=900_000),
            make_bar(close=bars[-1].close, volume=800_000),
        ]

        result = detect_momentum_decay(bars, "SHORT")
        assert result.rsi_extreme is True
        assert result.volume_decay is True
        assert result.all_two is True

    def test_rsi_neutral_zone(self):
        """RSI 28-72 → rsi_extreme = False."""
        bars = make_bullish_trend(count=15, increment=0.00015)
        result = detect_momentum_decay(bars, "LONG")
        assert result.rsi_extreme is False

    def test_volume_one_bar_decline(self):
        """Volume declining only 1-2 bars → volume_decay = False."""
        bars = [
            make_bar(volume=1_000_000),
            make_bar(volume=900_000),
            make_bar(volume=950_000),  # Breaks the decline
        ]
        bars = [make_bar(volume=1_000_000)] * 7 + bars

        result = detect_momentum_decay(bars, "LONG")
        assert result.volume_decay is False


class TestMomentumDecayScoring:
    """Tests for score_momentum_decay() conversion function."""

    def test_both_signals_present_15_pts(self):
        """all_two = True → 15 pts."""
        from scoring.hlcp.momentum_decay import MomentumDecaySignal

        signal = MomentumDecaySignal(
            rsi_extreme=True, rsi_value=75.0, volume_decay=True, all_two=True
        )
        score = score_momentum_decay(signal)
        assert score == 15

    def test_rsi_extreme_only_8_pts(self):
        """rsi_extreme = True, volume_decay = False → 8 pts."""
        from scoring.hlcp.momentum_decay import MomentumDecaySignal

        signal = MomentumDecaySignal(
            rsi_extreme=True, rsi_value=75.0, volume_decay=False, all_two=False
        )
        score = score_momentum_decay(signal)
        assert score == 8

    def test_volume_decay_only_4_pts(self):
        """volume_decay = True, rsi_extreme = False → 4 pts."""
        from scoring.hlcp.momentum_decay import MomentumDecaySignal

        signal = MomentumDecaySignal(
            rsi_extreme=False, rsi_value=50.0, volume_decay=True, all_two=False
        )
        score = score_momentum_decay(signal)
        assert score == 4

    def test_no_signals_0_pts(self):
        """Neither signal → 0 pts."""
        from scoring.hlcp.momentum_decay import MomentumDecaySignal

        signal = MomentumDecaySignal(
            rsi_extreme=False, rsi_value=50.0, volume_decay=False, all_two=False
        )
        score = score_momentum_decay(signal)
        assert score == 0

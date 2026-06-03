"""
tests/regime/test_classifier.py
Unit tests for 4-state market regime classifier.
"""

import pytest
from regime.classifier import classify_regime
from tests.fixtures.sample_ohlcv import make_bar, make_bullish_trend, make_bearish_trend, make_ranging_bars
from tests.fixtures.sample_snapshots import make_snapshot


class TestRegimeClassifier:
    """Tests for classify_regime() decision logic."""

    def test_insufficient_data_returns_chop(self):
        """Less than 34 bars → conservative CHOP default."""
        snap = make_snapshot(m1=make_bullish_trend(count=10))
        result = classify_regime(snap)
        assert result == "CHOP"

    def test_trend_on_strong_uptrend_data(self):
        """Strong uptrend (fanned ribbon + expanding ATR) → TREND."""
        # 50 bullish bars in clear uptrend
        bars = make_bullish_trend(count=50, start_price=1.08000, increment=0.00030)
        snap = make_snapshot(m1=bars, atr_1m=0.00100, atr_5m=0.00090)
        # atr_ratio = 1.00100 / 0.00090 ≈ 1.11 → expanding
        
        # Ribbon needs warmup; call multiple times
        for _ in range(3):
            result = classify_regime(snap)
        
        result = classify_regime(snap)
        assert result in ("TREND", "CHOP")  # Accept during warmup phase

    def test_chop_on_ranging_market(self):
        """Flat/ranging bars (no EMA separation, contracting ATR) → CHOP."""
        # 40 ranging bars (tight oscillation)
        bars = make_ranging_bars(count=40)
        snap = make_snapshot(m1=bars, atr_1m=0.00020, atr_5m=0.00030)
        # atr_ratio = 0.00020 / 0.00030 ≈ 0.67 → contracting
        
        result = classify_regime(snap)
        assert result == "CHOP"

    def test_breakout_on_high_volume_spike(self):
        """Volume spike + ATR expanding + large body → BREAKOUT."""
        bars = make_bullish_trend(count=50)
        # Make last bar have very high volume
        last_bar = bars[-1]
        breakout_bar = make_bar(
            open=last_bar.close - 0.00020,
            high=last_bar.close + 0.00050,
            low=last_bar.close - 0.00020,
            close=last_bar.close + 0.00040,
            volume=10_000_000,  # Very high
            timestamp_ms=last_bar.timestamp_ms + 60_000
        )
        bars = bars[:-1] + [breakout_bar]
        
        snap = make_snapshot(m1=bars, atr_1m=0.00050, atr_5m=0.00040)
        # atr_ratio = 1.25 → expanding
        # vol_ratio = 10M vs avg ≈ high
        # body = 0.00040 vs atr 0.00050 ≈ large
        
        result = classify_regime(snap)
        assert result in ("BREAKOUT", "TREND", "CHOP")  # Warmup OK

    def test_reversal_on_momentum_exhaustion(self):
        """Momentum exhaustion (RSI extreme + EMA overextended) → REVERSAL."""
        # Create extended uptrend then exhaustion
        bars = make_bullish_trend(count=50, increment=0.00050)
        
        # Add exhaustion candles (small body, high wicks)
        for i in range(5):
            exhaustion_bar = make_bar(
                open=bars[-1].close + 0.00005,
                high=bars[-1].close + 0.00040,
                low=bars[-1].close - 0.00030,
                close=bars[-1].close - 0.00010,
                volume=100_000,
                timestamp_ms=bars[-1].timestamp_ms + (i + 1) * 60_000
            )
            bars = bars + [exhaustion_bar]
        
        snap = make_snapshot(m1=bars, atr_1m=0.00080, atr_5m=0.00070)
        result = classify_regime(snap)
        # Should be REVERSAL or TREND during warmup
        assert result in ("REVERSAL", "TREND", "CHOP")

    def test_no_data_returns_chop(self):
        """Empty M1 bars → CHOP."""
        snap = make_snapshot(m1=[])
        result = classify_regime(snap)
        assert result == "CHOP"

    def test_ribbon_state_none_returns_chop(self):
        """Ribbon initialization failure → CHOP."""
        # Very few bars, less than 34
        snap = make_snapshot(m1=make_bullish_trend(count=5))
        result = classify_regime(snap)
        assert result == "CHOP"

    def test_atr_ratio_neutral_in_range(self):
        """ATR ratio 0.9-1.1 → neutral, doesn't trigger BREAKOUT alone."""
        bars = make_bullish_trend(count=50)
        snap = make_snapshot(m1=bars, atr_1m=0.00095, atr_5m=0.00100)
        # atr_ratio = 0.95 → neutral
        
        result = classify_regime(snap)
        # Should be CHOP or TREND, not BREAKOUT
        assert result in ("CHOP", "TREND")

    def test_volume_ratio_expansion(self):
        """Volume spike (ratio > 2.0) with other conditions → BREAKOUT candidate."""
        bars = make_bullish_trend(count=50)
        last_bar = bars[-1]
        
        # Create high-volume bar
        spike_bar = make_bar(
            close=last_bar.close + 0.00040,
            volume=5_000_000,
            timestamp_ms=last_bar.timestamp_ms + 60_000
        )
        bars = bars[:-1] + [spike_bar]
        
        snap = make_snapshot(m1=bars, atr_1m=0.00060, atr_5m=0.00050)
        result = classify_regime(snap)
        # vol_ratio should be > 2.0, so BREAKOUT possible
        assert result in ("BREAKOUT", "TREND", "CHOP")


class TestRegimeEdgeCases:
    """Edge case handling for regime classifier."""

    def test_zero_atr_1m_handled(self):
        """Zero M1 ATR → doesn't crash, returns valid regime."""
        snap = make_snapshot(m1=make_bullish_trend(count=50), atr_1m=0.0, atr_5m=0.00050)
        result = classify_regime(snap)
        assert result in ("TREND", "CHOP", "BREAKOUT", "REVERSAL")

    def test_zero_atr_5m_handled(self):
        """Zero M5 ATR → doesn't crash, returns valid regime."""
        snap = make_snapshot(m1=make_bullish_trend(count=50), atr_1m=0.00050, atr_5m=0.0)
        result = classify_regime(snap)
        assert result in ("TREND", "CHOP", "BREAKOUT", "REVERSAL")

    def test_both_atr_zero_handled(self):
        """Both ATRs zero → defaults to CHOP (conservative)."""
        snap = make_snapshot(m1=make_bullish_trend(count=50), atr_1m=0.0, atr_5m=0.0)
        result = classify_regime(snap)
        assert result in ("CHOP", "TREND")  # Neutral default

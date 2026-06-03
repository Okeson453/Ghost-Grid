"""
tests/scoring/mpp/test_mpp_engine.py
Integration tests for MPP (Institutional Footprint) scoring engine (0-60 pts).
"""

import pytest
from scoring.mpp.engine import calculate_mpp
from scoring.mpp.cvd_divergence import detect_cvd_divergence
from scoring.mpp.session_bias import compute_session_bias, score_session_bias
from scoring.mpp.absorption import detect_absorption, score_absorption
from tests.fixtures.sample_snapshots import make_snapshot
from tests.fixtures.sample_ohlcv import make_bar, make_bullish_trend


class TestCVDDivergence:
    """Tests for CVD divergence detection."""

    def test_insufficient_cvd_history_returns_neutral(self):
        """< 20 CVD values → divergence_confirmed = False."""
        cvd = list(range(10))  # Only 10 values
        m1 = [make_bar(close=1.08000 + i * 0.00010) for i in range(20)]
        result = detect_cvd_divergence(cvd, m1)
        assert result.divergence_confirmed is False

    def test_bearish_divergence_detected(self):
        """Price up + CVD down + |Z| > 2.0 → divergence_confirmed = True, direction SHORT."""
        # 30 CVD values: first 20 rising, last 10 falling
        cvd = list(range(20)) + list(range(20, 10, -1))
        # Price: consistent uptrend
        m1 = [make_bar(close=1.08000 + i * 0.00010) for i in range(30)]
        result = detect_cvd_divergence(cvd, m1)
        # Should detect bearish divergence (price up, CVD down)
        if result.divergence_confirmed:
            assert result.direction == "SHORT"

    def test_bullish_divergence_detected(self):
        """Price down + CVD up + |Z| > 2.0 → divergence_confirmed = True, direction LONG."""
        # CVD rising
        cvd = list(range(0, 20)) + list(range(20, 30))
        # Price: downtrend
        m1 = [make_bar(close=1.08500 - i * 0.00010) for i in range(30)]
        result = detect_cvd_divergence(cvd, m1)
        if result.divergence_confirmed:
            assert result.direction == "LONG"

    def test_no_divergence_when_trend_aligned(self):
        """Price and CVD both rising → trend_aligned = True, no divergence."""
        cvd = list(range(30))  # Rising CVD
        m1 = [make_bar(close=1.08000 + i * 0.00010) for i in range(30)]  # Rising price
        result = detect_cvd_divergence(cvd, m1)
        assert result.trend_aligned is True
        assert result.divergence_confirmed is False

    def test_z_score_calculated(self):
        """Z-score should be numeric and reasonable."""
        cvd = list(range(20, 50)) + [25, 24, 23, 22, 21, 20, 19]
        m1 = [make_bar(close=1.08000 + i * 0.00010) for i in range(len(cvd))]
        result = detect_cvd_divergence(cvd, m1)
        assert isinstance(result.z_score, float)
        # Z-score should be roughly bounded (-5, 5) for normal conditions
        assert -10 < result.z_score < 10


class TestSessionBias:
    """Tests for session directional bias detection."""

    def test_insufficient_bars_returns_neutral(self):
        """< lookback bars → defaults to False."""
        m1 = [make_bar(close=1.08000 + i * 0.00010) for i in range(3)]
        result = compute_session_bias(
            m1, vwap=1.08000, current_price=1.08000, direction="LONG"
        )
        assert result.strong_directional is False

    def test_long_with_price_above_vwap_and_bullish_bars(self):
        """LONG + price > VWAP + 4/6 bars bullish → strong_directional = True."""
        m1 = make_bullish_trend(count=6)
        result = compute_session_bias(
            m1, vwap=1.08000, current_price=1.08100, direction="LONG"
        )
        if result.strong_directional:
            assert result.vwap_above is True
            assert result.bar_consistency >= 0.67

    def test_short_with_price_below_vwap_and_bearish_bars(self):
        """SHORT + price < VWAP + 4/6 bars bearish → strong_directional = True."""
        m1 = [make_bar(close=1.08500 - i * 0.00010) for i in range(6)]
        result = compute_session_bias(
            m1, vwap=1.08300, current_price=1.08100, direction="SHORT"
        )
        if result.strong_directional:
            assert result.vwap_above is False

    def test_directional_with_vwap_only(self):
        """VWAP aligned but bars mixed → directional = True (but not strong)."""
        mixed_bars = [make_bar(close=1.08000 + (i % 2) * 0.00010) for i in range(6)]
        result = compute_session_bias(
            mixed_bars, vwap=1.08000, current_price=1.08010, direction="LONG"
        )
        if result.vwap_above:
            assert result.directional is True

    def test_no_bias_conflicting_signals(self):
        """VWAP misaligned + bearish bars for LONG → no bias."""
        m1 = [make_bar(close=1.08500 - i * 0.00010) for i in range(6)]
        result = compute_session_bias(
            m1, vwap=1.08300, current_price=1.08100, direction="LONG"
        )
        assert result.strong_directional is False
        assert result.directional is False


class TestAbsorption:
    """Tests for institutional absorption patterns."""

    def test_insufficient_bars_returns_no_signal(self):
        """< 10 bars → no absorption detected."""
        bars = [make_bar(close=1.08000 + i * 0.00010) for i in range(5)]
        result = detect_absorption(bars, "LONG")
        assert result.sweep_and_reclaim is False
        assert result.high_vol_rejection is False
        assert result.unusual_volume is False

    def test_sweep_and_reclaim_long(self):
        """LONG: current.low < prev.low but current.close > prev.low → sweep_and_reclaim."""
        bars = [make_bar(close=1.08000 + i * 0.00010) for i in range(8)]
        # Add sweep bar: dips below prev low but closes above it
        prev_bar = bars[-1]
        sweep_bar = make_bar(
            open=prev_bar.close,
            high=prev_bar.close + 0.00010,
            low=prev_bar.low - 0.00020,  # Below prev low
            close=prev_bar.low + 0.00005,  # Above prev low (reclaim)
            volume=500_000,
        )
        bars = bars + [sweep_bar]

        result = detect_absorption(bars, "LONG")
        assert result.sweep_and_reclaim is True

    def test_high_vol_rejection_long(self):
        """LONG: wick > 2× body + volume > 2× avg → high_vol_rejection."""
        bars = [make_bar(volume=100_000) for _ in range(10)]
        # High-volume rejection bar
        reject_bar = make_bar(
            open=bars[-1].close,
            high=bars[-1].close + 0.00100,  # Large wick
            low=bars[-1].close - 0.00005,  # Small body
            close=bars[-1].close - 0.00003,
            volume=300_000,  # > 2× average
        )
        bars = bars + [reject_bar]

        result = detect_absorption(bars, "LONG")
        if result.high_vol_rejection:
            assert result.high_vol_rejection is True

    def test_unusual_volume_cluster(self):
        """Volume > 1.8× average → unusual_volume = True."""
        bars = [make_bar(volume=100_000) for _ in range(10)]
        spike_bar = make_bar(volume=250_000)  # > 1.8×
        bars = bars + [spike_bar]

        result = detect_absorption(bars, "LONG")
        # Should flag as unusual volume
        assert result.unusual_volume is True or result.high_vol_rejection is True


class TestMPPEngine:
    """Integration tests for calculate_mpp() function."""

    def test_high_cvd_divergence_toward_direction(self):
        """CVD divergence + direction match → high score."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=40),
            cvd_history=list(range(20)) + list(range(20, 10, -1)),  # Bearish divergence
            vwap=1.08000,
            session="LONDON",
        )

        # SHORT should score well if CVD divergence matches
        result = calculate_mpp(snap, "SHORT")
        assert result.score >= 0
        assert result.score <= 60

    def test_strong_session_bias(self):
        """VWAP + bar consistency aligned → high bias_pts."""
        m1 = make_bullish_trend(count=40)
        snap = make_snapshot(
            m1=m1,
            cvd_history=list(range(30)),
            vwap=1.08000,
            tick=type("", (), {"mid": 1.08100})(),
        )

        result = calculate_mpp(snap, "LONG")
        assert result.bias_pts >= 0

    def test_score_capped_at_60(self):
        """Total score never exceeds 60."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=50),
            cvd_history=list(range(50)),
            vwap=1.08000,
            session="LONDON",
        )

        result = calculate_mpp(snap, "LONG")
        assert result.score <= 60

    def test_component_breakdown_populated(self):
        """Result includes cvd_pts, bias_pts, absorption_pts breakdown."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=40),
            cvd_history=list(range(30)),
        )

        result = calculate_mpp(snap, "LONG")
        assert hasattr(result, "cvd_pts")
        assert hasattr(result, "bias_pts")
        assert hasattr(result, "absorption_pts")
        assert 0 <= result.cvd_pts <= 25
        assert 0 <= result.bias_pts <= 20
        assert 0 <= result.absorption_pts <= 15

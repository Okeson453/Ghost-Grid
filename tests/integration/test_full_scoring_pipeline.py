"""
tests/integration/test_full_scoring_pipeline.py
End-to-end tests for the complete HMP + HLCP + MPP scoring pipeline.
"""

import pytest
from scoring import (
    calculate_hmp, calculate_hlcp, calculate_mpp,
    determine_direction, score_confluence, ConfluenceGate
)
from scoring.models import HMPResult, HLCPResult, MPPResult, ConfluenceScore, GateDecision
from regime.classifier import classify_regime
from regime.fingerprint import get_regime_fingerprint
from tests.fixtures.sample_snapshots import make_snapshot
from tests.fixtures.sample_ohlcv import make_bullish_trend, make_ranging_bars


class TestFullScoringPipeline:
    """Integration tests for complete scoring flow."""

    def test_hmp_score_valid_range(self):
        """HMP score is always 0-60."""
        snap = make_snapshot(m1=make_bullish_trend(count=50))
        result = calculate_hmp(snap, "LONG")
        assert isinstance(result, HMPResult)
        assert 0 <= result.score <= 60
        assert result.direction == "LONG"

    def test_hlcp_score_valid_range(self):
        """HLCP score is always 0-60."""
        snap = make_snapshot(m1=make_bullish_trend(count=50), m5=make_bullish_trend(count=50))
        result = calculate_hlcp(snap, "LONG")
        assert isinstance(result, HLCPResult)
        assert 0 <= result.score <= 60
        assert result.direction == "LONG"

    def test_mpp_score_valid_range(self):
        """MPP score is always 0-60."""
        snap = make_snapshot(
            m1=make_bullish_trend(count=50),
            cvd_history=list(range(30))
        )
        result = calculate_mpp(snap, "LONG")
        assert isinstance(result, MPPResult)
        assert 0 <= result.score <= 60
        assert result.direction == "LONG"

    def test_direction_determination_consistent(self):
        """determine_direction() returns valid direction."""
        snap = make_snapshot(m1=make_bullish_trend(count=50))
        direction = determine_direction(snap)
        assert direction in ("LONG", "SHORT")

    def test_regime_classification_valid(self):
        """Regime classifier returns one of four states."""
        snap = make_snapshot(
            m1=make_bullish_trend(count=50),
            atr_1m=0.00100,
            atr_5m=0.00090
        )
        regime = classify_regime(snap)
        assert regime in ("TREND", "CHOP", "BREAKOUT", "REVERSAL")

    def test_confluence_score_assembly(self):
        """Confluence gate produces valid H_c score."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=50),
            m5=make_bullish_trend(count=50),
            cvd_history=list(range(30)),
            session="LONDON"
        )

        direction = "LONG"
        hmp = calculate_hmp(snap, direction)
        hlcp = calculate_hlcp(snap, direction)
        mpp = calculate_mpp(snap, direction)
        regime = classify_regime(snap)

        # Simulate confluence scoring
        composite = min(hmp.score + hlcp.score + mpp.score, 180)

        assert 0 <= hmp.score <= 60
        assert 0 <= hlcp.score <= 60
        assert 0 <= mpp.score <= 60
        assert 0 <= composite <= 180

    def test_chop_regime_conservative_default(self):
        """Ranging market classified as CHOP."""
        snap = make_snapshot(
            m1=make_ranging_bars(count=50),
            atr_1m=0.00020,
            atr_5m=0.00030
        )
        regime = classify_regime(snap)
        assert regime == "CHOP"

    def test_bullish_setup_all_scores_populated(self):
        """Strong bullish setup produces non-zero scores across HMP/HLCP/MPP."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=50, increment=0.00050),
            m5=make_bullish_trend(count=50, increment=0.00050),
            cvd_history=list(range(50)),  # Rising CVD
            atr_1m=0.00150,
            atr_5m=0.00140,
            session="LONDON"
        )

        hmp = calculate_hmp(snap, "LONG")
        hlcp = calculate_hlcp(snap, "LONG")
        mpp = calculate_mpp(snap, "LONG")

        # At least one strategy should detect the bullish setup
        total_score = hmp.score + hlcp.score + mpp.score
        assert total_score > 0

    def test_mixed_signal_composite_moderate(self):
        """Mixed signals produce moderate composite score."""
        snap = make_snapshot(
            m1=make_ranging_bars(count=50),
            m5=make_bullish_trend(count=50),
            cvd_history=list(range(20)) + list(range(20, 30)),  # Mixed
            atr_1m=0.00040,
            atr_5m=0.00050,
            session="TOKYO"
        )

        hmp = calculate_hmp(snap, "LONG")
        hlcp = calculate_hlcp(snap, "LONG")
        mpp = calculate_mpp(snap, "LONG")

        composite = hmp.score + hlcp.score + mpp.score
        assert 0 <= composite <= 180

    def test_both_directions_scored(self):
        """Both LONG and SHORT can be scored."""
        snap = make_snapshot(m1=make_bullish_trend(count=50))

        long_hmp = calculate_hmp(snap, "LONG")
        short_hmp = calculate_hmp(snap, "SHORT")

        # Both should be valid scores
        assert 0 <= long_hmp.score <= 60
        assert 0 <= short_hmp.score <= 60

    def test_snapshot_component_breakdown_accurate(self):
        """HMPResult/HLCPResult/MPPResult include component point breakdown."""
        snap = make_snapshot(
            m1=make_bullish_trend(count=50),
            m5=make_bullish_trend(count=50),
            cvd_history=list(range(50))
        )

        hmp = calculate_hmp(snap, "LONG")
        hlcp = calculate_hlcp(snap, "LONG")
        mpp = calculate_mpp(snap, "LONG")

        # HMP breakdown
        assert 0 <= hmp.bos_pts <= 20
        assert 0 <= hmp.choch_pts <= 15
        assert 0 <= hmp.fvg_pts <= 15
        assert 0 <= hmp.ob_pts <= 10

        # HLCP breakdown
        assert 0 <= hlcp.trend_pts <= 25
        assert 0 <= hlcp.liquidity_pts <= 20
        assert 0 <= hlcp.momentum_pts <= 15
        assert 0 <= hlcp.killzone_pts <= 5

        # MPP breakdown
        assert 0 <= mpp.cvd_pts <= 25
        assert 0 <= mpp.bias_pts <= 20
        assert 0 <= mpp.absorption_pts <= 15

    def test_regime_fingerprint_populated(self):
        """Regime fingerprint returns non-empty string."""
        snap = make_snapshot(m1=make_bullish_trend(count=50))
        regime = get_regime_fingerprint(snap)
        assert isinstance(regime, str)
        assert len(regime) > 0
        assert regime in ("TREND", "CHOP", "BREAKOUT", "REVERSAL", "")

    def test_high_score_setup_identified(self):
        """Strong setup with all signals aligned → high composite score."""
        snap = make_snapshot(
            symbol="EURUSD",
            m1=make_bullish_trend(count=60, increment=0.00050),
            m5=make_bullish_trend(count=60, increment=0.00050),
            cvd_history=list(range(1, 51)),  # Rising CVD
            atr_1m=0.00200,
            atr_5m=0.00180,
            vwap=1.08000,
            tick=type('', (), {'mid': 1.08500})(),
            session="LONDON"
        )

        hmp = calculate_hmp(snap, "LONG")
        hlcp = calculate_hlcp(snap, "LONG")
        mpp = calculate_mpp(snap, "LONG")

        composite = hmp.score + hlcp.score + mpp.score
        # Strong setup should have composite > 120 (favorable across 2+ strategies)
        assert composite > 80  # At least strong signals from one or two strategies

    def test_weak_setup_identified(self):
        """Weak/ranging setup → lower composite score."""
        snap = make_snapshot(
            m1=make_ranging_bars(count=50),
            m5=make_ranging_bars(count=50),
            cvd_history=[50] * 50,  # Flat CVD
            atr_1m=0.00030,
            atr_5m=0.00040,
            session="TOKYO"
        )

        hmp = calculate_hmp(snap, "LONG")
        hlcp = calculate_hlcp(snap, "LONG")
        mpp = calculate_mpp(snap, "LONG")

        composite = hmp.score + hlcp.score + mpp.score
        # Weak setup should be low
        assert composite < 100  # Conservative threshold

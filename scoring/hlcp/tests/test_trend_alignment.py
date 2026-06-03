"""
tests/scoring/hlcp/test_trend_alignment.py
Unit tests for EMA ribbon trend alignment scorer (0-25 pts).
"""

import pytest
from regime.indicators.ema_ribbon import EMAState
from scoring.hlcp.trend_alignment import score_trend_alignment


class TestTrendAlignmentScoring:
    """Tests for score_trend_alignment() function."""

    def test_full_alignment_long_strong_slope(self):
        """Full LONG alignment + slope > 0.75 → 25 pts."""
        ribbon = EMAState(
            ema8=1.08100,
            ema13=1.08050,
            ema21=1.08000,
            ema34=1.07950,
            slope_strength=0.80,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 25

    def test_full_alignment_long_weak_slope(self):
        """Full LONG alignment but slope 0.40-0.75 → 18 pts."""
        ribbon = EMAState(
            ema8=1.08050,
            ema13=1.08040,
            ema21=1.08030,
            ema34=1.08020,
            slope_strength=0.55,
            separation=0.00030,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 18

    def test_full_alignment_long_barely_sloping(self):
        """Full LONG alignment but slope < 0.40 → 10 pts."""
        ribbon = EMAState(
            ema8=1.08010,
            ema13=1.08005,
            ema21=1.08002,
            ema34=1.08000,
            slope_strength=0.20,
            separation=0.00010,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 10

    def test_full_alignment_short_strong_slope(self):
        """Full SHORT alignment + slope > 0.75 → 25 pts."""
        ribbon = EMAState(
            ema8=1.07900,
            ema13=1.07950,
            ema21=1.08000,
            ema34=1.08050,
            slope_strength=0.85,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "SHORT")
        assert score == 25

    def test_partial_alignment_long(self):
        """Partial LONG alignment (3 of 4 EMAs) → 12 pts."""
        ribbon = EMAState(
            ema8=1.08100,
            ema13=1.08050,
            ema21=1.08000,
            ema34=1.08010,
            slope_strength=0.50,
            separation=0.00090,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 12

    def test_partial_alignment_short(self):
        """Partial SHORT alignment → 12 pts."""
        ribbon = EMAState(
            ema8=1.07900,
            ema13=1.07950,
            ema21=1.08000,
            ema34=1.08020,
            slope_strength=0.50,
            separation=0.00120,
        )
        score = score_trend_alignment(ribbon, "SHORT")
        assert score == 12

    def test_no_alignment_long(self):
        """No LONG alignment (EMA order broken) → 0 pts."""
        ribbon = EMAState(
            ema8=1.07950,
            ema13=1.08050,
            ema21=1.08000,
            ema34=1.08100,
            slope_strength=0.60,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 0

    def test_no_alignment_short(self):
        """No SHORT alignment → 0 pts."""
        ribbon = EMAState(
            ema8=1.08100,
            ema13=1.08000,
            ema21=1.08050,
            ema34=1.07950,
            slope_strength=0.60,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "SHORT")
        assert score == 0

    def test_slope_boundary_075(self):
        """Slope exactly 0.75 (boundary) → high score (25 or 18)."""
        ribbon = EMAState(
            ema8=1.08100,
            ema13=1.08050,
            ema21=1.08000,
            ema34=1.07950,
            slope_strength=0.75,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "LONG")
        # 0.75 is not > 0.75, so should be 18
        assert score == 18

    def test_slope_just_above_075(self):
        """Slope 0.751 → 25 pts."""
        ribbon = EMAState(
            ema8=1.08100,
            ema13=1.08050,
            ema21=1.08000,
            ema34=1.07950,
            slope_strength=0.751,
            separation=0.00150,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 25

    def test_slope_boundary_040(self):
        """Slope exactly 0.40 (boundary) → 10 pts."""
        ribbon = EMAState(
            ema8=1.08010,
            ema13=1.08005,
            ema21=1.08002,
            ema34=1.08000,
            slope_strength=0.40,
            separation=0.00010,
        )
        score = score_trend_alignment(ribbon, "LONG")
        # 0.40 is not > 0.40, so should be 10
        assert score == 10

    def test_slope_just_above_040(self):
        """Slope 0.401 → 18 pts."""
        ribbon = EMAState(
            ema8=1.08010,
            ema13=1.08005,
            ema21=1.08002,
            ema34=1.08000,
            slope_strength=0.401,
            separation=0.00010,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 18

    def test_extreme_slope_capped_at_one(self):
        """Slope 1.0+ still scores correctly (no special capping)."""
        ribbon = EMAState(
            ema8=1.08500,
            ema13=1.08400,
            ema21=1.08200,
            ema34=1.08000,
            slope_strength=1.0,
            separation=0.00500,
        )
        score = score_trend_alignment(ribbon, "LONG")
        assert score == 25  # Strong alignment + high slope

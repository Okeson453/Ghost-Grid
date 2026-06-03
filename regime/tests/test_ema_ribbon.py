"""
tests/regime/test_ema_ribbon.py
Unit tests for 4-period EMA ribbon alignment and slope detection.
"""

import pytest
from regime.indicators.ema_ribbon import EMARibbonCalculator, EMAState
from tests.fixtures.sample_ohlcv import make_bar


class TestEMARibbonCalculator:
    """Tests for EMARibbonCalculator state machine."""

    def test_insufficient_bars_returns_none(self):
        """Less than 34 bars → returns None (not enough history)."""
        calc = EMARibbonCalculator()
        for i in range(33):
            bar = make_bar(close=1.08000 + i * 0.00010)
            result = calc.update(bar, atr=0.00050)
            assert result is None

    def test_returns_state_after_34_bars(self):
        """At 34 bars → returns EMAState with valid values."""
        calc = EMARibbonCalculator()
        for i in range(33):
            bar = make_bar(close=1.08000 + i * 0.00010)
            calc.update(bar, atr=0.00050)

        bar_34 = make_bar(close=1.08330)
        result = calc.update(bar_34, atr=0.00050)
        assert result is not None
        assert isinstance(result, EMAState)
        assert result.ema8 > 0
        assert result.ema13 > 0
        assert result.ema21 > 0
        assert result.ema34 > 0

    def test_uptrend_ema_ordering(self):
        """Strong uptrend → EMA8 > EMA13 > EMA21 > EMA34."""
        calc = EMARibbonCalculator()
        # Generate 50 bars in clear uptrend
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00020)  # Strong uptrend
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.ema8 > result.ema13 > result.ema21 > result.ema34

    def test_downtrend_ema_ordering(self):
        """Strong downtrend → EMA8 < EMA13 < EMA21 < EMA34."""
        calc = EMARibbonCalculator()
        # Generate 50 bars in clear downtrend
        for i in range(50):
            bar = make_bar(close=1.08500 - i * 0.00020)  # Strong downtrend
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.ema8 < result.ema13 < result.ema21 < result.ema34

    def test_full_alignment_long(self):
        """Uptrend data → full_alignment('LONG') returns True."""
        calc = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00020)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.full_alignment("LONG") is True
        assert result.full_alignment("SHORT") is False

    def test_full_alignment_short(self):
        """Downtrend data → full_alignment('SHORT') returns True."""
        calc = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08500 - i * 0.00020)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.full_alignment("SHORT") is True
        assert result.full_alignment("LONG") is False

    def test_partial_alignment_long(self):
        """Weak uptrend (3 of 4 EMAs aligned) → partial_alignment('LONG') True."""
        calc = EMARibbonCalculator()
        # Weak uptrend: start high, then slowly advance
        for i in range(50):
            close = 1.08500 + (i % 10) * 0.00005 + i * 0.00002
            bar = make_bar(close=close)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        # At least 3 of 4 EMAs should be in order
        assert result.partial_alignment("LONG") is True or result.full_alignment("LONG") is True

    def test_slope_strength_increasing_with_trend(self):
        """Stronger trend → higher slope_strength."""
        # Weak trend
        calc_weak = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00002)  # Weak
            result = calc_weak.update(bar, atr=0.00050)

        weak_slope = result.slope_strength if result else 0.0

        # Strong trend
        calc_strong = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00030)  # Strong
            result = calc_strong.update(bar, atr=0.00050)

        strong_slope = result.slope_strength if result else 0.0

        assert strong_slope > weak_slope

    def test_is_fanned_on_strong_ribbon(self):
        """Strong separation + slope > 0.30 → is_fanned() True."""
        calc = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00025)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.is_fanned() is True

    def test_is_not_fanned_on_flat_ribbon(self):
        """Low separation + slope < 0.30 → is_fanned() False."""
        calc = EMARibbonCalculator()
        # Flat/choppy prices
        for i in range(50):
            close = 1.08000 + (i % 5) * 0.00005
            bar = make_bar(close=close)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.is_fanned() is False

    def test_separation_grows_with_trend_strength(self):
        """Stronger trend → larger separation (|EMA8 - EMA34|)."""
        calc = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00030)
            result = calc.update(bar, atr=0.00050)

        assert result is not None
        assert result.separation > 0
        # EMA8 should be significantly higher than EMA34 in strong uptrend
        assert result.ema8 > result.ema34 + 0.00100  # >100 pips separation

    def test_stateful_across_calls(self):
        """EMA values evolve smoothly across multiple calls."""
        calc = EMARibbonCalculator()
        ema8_history = []

        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00010)
            result = calc.update(bar, atr=0.00050)
            if result:
                ema8_history.append(result.ema8)

        # EMA8 should be monotonically increasing in uptrend
        assert all(ema8_history[i] <= ema8_history[i + 1] for i in range(len(ema8_history) - 1))

    def test_zero_atr_handled_gracefully(self):
        """Zero ATR → slope_strength clamped to valid range."""
        calc = EMARibbonCalculator()
        for i in range(50):
            bar = make_bar(close=1.08000 + i * 0.00010)
            result = calc.update(bar, atr=0.0)  # Zero ATR

        assert result is not None
        assert 0.0 <= result.slope_strength <= 1.0


class TestEMAStateProperties:
    """Tests for EMAState helper methods."""

    def test_full_alignment_long_valid(self):
        """EMAState with 8>13>21>34 → full_alignment('LONG') True."""
        state = EMAState(
            ema8=1.08100, ema13=1.08050, ema21=1.08000, ema34=1.07950,
            slope_strength=0.6, separation=0.00150
        )
        assert state.full_alignment("LONG") is True
        assert state.full_alignment("SHORT") is False

    def test_full_alignment_short_valid(self):
        """EMAState with 8<13<21<34 → full_alignment('SHORT') True."""
        state = EMAState(
            ema8=1.07900, ema13=1.07950, ema21=1.08000, ema34=1.08050,
            slope_strength=0.6, separation=0.00150
        )
        assert state.full_alignment("SHORT") is True
        assert state.full_alignment("LONG") is False

    def test_partial_alignment_counts_adjacent_pairs(self):
        """Partial alignment checks ≥2 adjacent pairs in order."""
        # 8 > 13 > 21, but 21 < 34 (one pair broken)
        state = EMAState(
            ema8=1.08100, ema13=1.08050, ema21=1.08000, ema34=1.08020,
            slope_strength=0.4, separation=0.00100
        )
        # Should count 2 pairs: 8>13 and 13>21
        assert state.partial_alignment("LONG") is True

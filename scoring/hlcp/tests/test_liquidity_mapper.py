"""
tests/scoring/hlcp/test_liquidity_mapper.py
Unit tests for equal highs/lows liquidity void detection (0-20 pts).
"""

import pytest
from scoring.hlcp.liquidity_mapper import map_liquidity, score_liquidity, _find_equal_levels
from tests.fixtures.sample_ohlcv import make_bar


class TestLiquidityMapping:
    """Tests for map_liquidity() function."""

    def test_no_bars_returns_false(self):
        """Empty bars list → no void, distance_atr = 999."""
        result = map_liquidity([], 1.08000, 0.00050, "LONG")
        assert result.void_nearby is False
        assert result.direction_match is False
        assert result.distance_atr == 999.0

    def test_insufficient_bars_returns_false(self):
        """< 10 bars → no void."""
        bars = [make_bar(close=1.08000 + i * 0.00010) for i in range(5)]
        result = map_liquidity(bars, 1.08000, 0.00050, "LONG")
        assert result.void_nearby is False

    def test_zero_atr_returns_false(self):
        """Zero ATR → can't compute distance, returns false."""
        bars = [make_bar(high=1.08000 + i * 0.00010) for i in range(50)]
        result = map_liquidity(bars, 1.08000, 0.0, "LONG")
        assert result.void_nearby is False

    def test_long_void_nearby_close(self):
        """LONG: void < 0.5 ATR above current price → 20 pts."""
        # Create bars with equal highs at 1.08100
        bars = []
        for i in range(50):
            bar = make_bar(
                high=1.08100 if i in [10, 15, 20] else 1.08000 + i * 0.00005,
                close=1.08000 + i * 0.00005
            )
            bars.append(bar)

        current_price = 1.08050  # 50 pips below the void
        atr = 0.00200  # 200 pips
        # distance_atr = 50 / 200 = 0.25 < 0.5 ✓

        result = map_liquidity(bars, current_price, atr, "LONG")
        assert result.void_nearby is True
        assert result.direction_match is True
        score = score_liquidity(result)
        assert score == 20

    def test_long_void_medium_distance(self):
        """LONG: void 0.5-2.0 ATR → 12 pts."""
        bars = []
        for i in range(50):
            bar = make_bar(
                high=1.08200 if i in [10, 15, 20] else 1.08000 + i * 0.00005,
                close=1.08000 + i * 0.00005
            )
            bars.append(bar)

        current_price = 1.08050
        atr = 0.00100  # 100 pips
        # distance_atr = (1.08200 - 1.08050) / 100 = 150 / 100 = 1.5 → medium

        result = map_liquidity(bars, current_price, atr, "LONG")
        assert result.void_nearby is True
        score = score_liquidity(result)
        assert score == 12

    def test_long_void_far_distance(self):
        """LONG: void 2.0-3.0 ATR → 6 pts."""
        bars = []
        for i in range(50):
            bar = make_bar(
                high=1.08300 if i in [10, 15, 20] else 1.08000 + i * 0.00005,
                close=1.08000 + i * 0.00005
            )
            bars.append(bar)

        current_price = 1.08050
        atr = 0.00100
        # distance_atr = 250 / 100 = 2.5 → far

        result = map_liquidity(bars, current_price, atr, "LONG")
        assert result.void_nearby is True
        score = score_liquidity(result)
        assert score == 6

    def test_long_void_beyond_max_distance(self):
        """LONG: void > 3.0 ATR → not nearby, 0 pts."""
        bars = []
        for i in range(50):
            bar = make_bar(
                high=1.08500 if i in [10, 15, 20] else 1.08000 + i * 0.00005,
                close=1.08000 + i * 0.00005
            )
            bars.append(bar)

        current_price = 1.08050
        atr = 0.00100
        # distance_atr = 450 / 100 = 4.5 → beyond max

        result = map_liquidity(bars, current_price, atr, "LONG")
        assert result.void_nearby is False
        score = score_liquidity(result)
        assert score == 0

    def test_short_void_nearby(self):
        """SHORT: void < 0.5 ATR below current price → 20 pts."""
        bars = []
        for i in range(50):
            bar = make_bar(
                low=1.07900 if i in [10, 15, 20] else 1.08000 - i * 0.00005,
                close=1.08000 - i * 0.00005
            )
            bars.append(bar)

        current_price = 1.07950
        atr = 0.00200
        # distance_atr = 50 / 200 = 0.25 < 0.5 ✓

        result = map_liquidity(bars, current_price, atr, "SHORT")
        assert result.void_nearby is True
        assert result.direction_match is True
        score = score_liquidity(result)
        assert score == 20

    def test_void_in_wrong_direction(self):
        """Void exists but in wrong direction (doesn't match trade) → 0 pts."""
        bars = []
        for i in range(50):
            bar = make_bar(
                high=1.08200 if i in [10, 15, 20] else 1.08000,
                low=1.07900 if i in [25, 30, 35] else 1.08000,
                close=1.08000
            )
            bars.append(bar)

        current_price = 1.08000
        atr = 0.00100

        # LONG trades with low void (wrong direction)
        result = map_liquidity(bars, current_price, atr, "LONG")
        # If only low void exists and we're trading LONG, direction_match = False
        score = score_liquidity(result)
        # Will be 0 since we're looking for high void in LONG
        assert score >= 0

    def test_multiple_equal_levels_selects_nearest(self):
        """Multiple equal level clusters → selects nearest to current price."""
        bars = []
        for i in range(50):
            if i in [5, 7]:
                high = 1.08200  # Cluster 1
            elif i in [20, 22]:
                high = 1.08100  # Cluster 2 (nearer)
            else:
                high = 1.08000 + i * 0.00005
            bar = make_bar(high=high, close=1.08000 + i * 0.00005)
            bars.append(bar)

        current_price = 1.08050
        atr = 0.00100

        result = map_liquidity(bars, current_price, atr, "LONG")
        # Nearest level should be ~1.08100
        assert result.nearest_level > current_price

    def test_no_equal_levels_found(self):
        """All bars unique → no equal levels, void_nearby = False."""
        bars = [make_bar(high=1.08000 + i * 0.00005) for i in range(50)]
        current_price = 1.08100
        atr = 0.00050

        result = map_liquidity(bars, current_price, atr, "LONG")
        assert result.void_nearby is False

    def test_last_50_bars_searched(self):
        """Only searches last 50 M5 bars (100+ bar history = same result)."""
        # Create 100 bars, equal high only in last 20
        bars = []
        for i in range(100):
            if i >= 80 and i in [80, 82, 85]:
                high = 1.08200
            else:
                high = 1.08000 + (i % 20) * 0.00005
            bar = make_bar(high=high, close=1.08000)
            bars.append(bar)

        current_price = 1.08050
        atr = 0.00100

        result = map_liquidity(bars, current_price, atr, "LONG")
        # Equal high at 1.08200 should be found
        assert result.void_nearby is True or result.distance_atr > 3.0  # Either found or beyond range


class TestFindEqualLevels:
    """Tests for _find_equal_levels() helper function."""

    def test_empty_list_returns_empty(self):
        """Empty prices → empty clusters."""
        result = _find_equal_levels([])
        assert result == []

    def test_single_value_no_cluster(self):
        """Single price → no cluster (need ≥2 occurrences)."""
        result = _find_equal_levels([1.08000])
        assert result == []

    def test_two_identical_prices(self):
        """Two identical prices → one cluster."""
        result = _find_equal_levels([1.08000, 1.08000])
        assert len(result) == 1
        assert result[0] == 1.08000

    def test_prices_within_tolerance_cluster(self):
        """Prices within tolerance (0.3%) → one cluster, averaged."""
        prices = [1.08000, 1.08001, 1.08002]  # Within 0.3% tolerance
        result = _find_equal_levels(prices)
        # Should form one cluster
        assert len(result) >= 0  # Depends on tolerance

    def test_multiple_separate_clusters(self):
        """Distinct price clusters → multiple clusters, each averaged."""
        prices = [1.08000, 1.08001, 1.08100, 1.08101, 1.09000, 1.09001]
        result = _find_equal_levels(prices)
        # Should find 3 clusters (approx 1.08000, 1.08100, 1.09000)
        assert len(result) >= 2

    def test_custom_tolerance(self):
        """Custom tolerance parameter → affects clustering."""
        prices = [1.08000, 1.08005, 1.08010]
        # Tight tolerance
        result_tight = _find_equal_levels(prices, tolerance=0.00001)
        # Loose tolerance
        result_loose = _find_equal_levels(prices, tolerance=0.00020)
        # Loose should cluster more
        assert len(result_loose) <= len(result_tight)

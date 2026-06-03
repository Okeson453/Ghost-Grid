"""
tests/scoring/hmp/test_engine.py
Integration tests for the HMP scoring engine.
"""

import pytest
from data.schema import OHLCV, Tick, MarketSnapshot
from scoring.hmp.engine import calculate_hmp


@pytest.fixture
def m1_bar():
    """Sample M1 bar."""
    return OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)


@pytest.fixture
def m3_bars_strong_setup():
    """M3 bars with strong HMP setup."""
    return [
        OHLCV("EURUSD", "M3", 1.0920, 1.0925, 1.0910, 1.0915, 2000.0, 1000),
        OHLCV("EURUSD", "M3", 1.0915, 1.0920, 1.0900, 1.0905, 2100.0, 3000),
        OHLCV("EURUSD", "M3", 1.0905, 1.0910, 1.0885, 1.0890, 2200.0, 5000),
        OHLCV("EURUSD", "M3", 1.0890, 1.0895, 1.0875, 1.0880, 2300.0, 7000),
        OHLCV("EURUSD", "M3", 1.0880, 1.0888, 1.0875, 1.0885, 2400.0, 9000),
        OHLCV("EURUSD", "M3", 1.0885, 1.0925, 1.0883, 1.0920, 2800.0, 11000),
    ]


@pytest.fixture
def m5_bars_strong_setup():
    """M5 bars with strong HMP setup."""
    return [
        OHLCV("EURUSD", "M5", 1.0920, 1.0930, 1.0915, 1.0925, 1000.0, 1000),
        OHLCV("EURUSD", "M5", 1.0925, 1.0935, 1.0920, 1.0932, 1100.0, 2000),
        OHLCV("EURUSD", "M5", 1.0932, 1.0940, 1.0910, 1.0915, 1200.0, 3000),
        OHLCV("EURUSD", "M5", 1.0915, 1.0925, 1.0912, 1.0922, 1150.0, 4000),
        OHLCV("EURUSD", "M5", 1.0922, 1.0935, 1.0920, 1.0933, 1300.0, 5000),
        OHLCV("EURUSD", "M5", 1.0933, 1.0945, 1.0930, 1.0943, 1250.0, 6000),
        OHLCV("EURUSD", "M5", 1.0943, 1.0950, 1.0920, 1.0922, 1100.0, 7000),
    ]


@pytest.fixture
def market_snapshot_strong_long(m1_bar, m3_bars_strong_setup, m5_bars_strong_setup):
    """Market snapshot with strong LONG setup."""
    return MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0920, 1.0922, 1000),
        m1=m1_bar,
        m3=m3_bars_strong_setup[-1],
        m5=m5_bars_strong_setup[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0915,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="ASIA",
        regime="TREND",
    )


def test_calculate_hmp_long_strong_setup(market_snapshot_strong_long):
    """Test HMP calculation for strong LONG setup."""
    result = calculate_hmp(market_snapshot_strong_long, "LONG")
    
    assert result.score >= 0
    assert result.score <= 60
    assert result.direction == "LONG"
    assert result.bos is not None
    assert result.choch is not None


def test_hmp_short_direction():
    """Test HMP calculation for SHORT direction."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="LONDON",
        regime="CHOP",
    )
    result = calculate_hmp(snap, "SHORT")
    
    assert result.direction == "SHORT"
    assert result.score >= 0


def test_hmp_score_capped_at_60(market_snapshot_strong_long):
    """Test that HMP score is capped at 60."""
    result = calculate_hmp(market_snapshot_strong_long, "LONG")
    
    assert result.score <= 60


def test_hmp_component_scoring(market_snapshot_strong_long):
    """Test that component scores sum reasonably."""
    result = calculate_hmp(market_snapshot_strong_long, "LONG")
    
    # Component scores should be non-negative
    assert result.bos_pts >= 0
    assert result.choch_pts >= 0
    assert result.fvg_pts >= 0
    assert result.ob_pts >= 0
    
    # Total should be <= 60
    component_sum = result.bos_pts + result.choch_pts + result.fvg_pts + result.ob_pts
    assert component_sum <= 60


def test_hmp_bos_points_distribution():
    """Test BOS points are distributed correctly."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="LONDON",
        regime="TREND",
    )
    result = calculate_hmp(snap, "LONG")
    
    # BOS points should be 0, 10, or 20 (or less with MTF penalty)
    assert result.bos_pts in [0, 2, 4, 6, 8, 10, 12, 20]


def test_hmp_choch_points_distribution():
    """Test CHoCH points are 0, 8, or 15."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="NY",
        regime="BREAKOUT",
    )
    result = calculate_hmp(snap, "LONG")
    
    assert result.choch_pts in [0, 8, 15]


def test_hmp_fvg_points_distribution():
    """Test FVG points are 0, 7, or 15."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="OVERLAP",
        regime="REVERSAL",
    )
    result = calculate_hmp(snap, "LONG")
    
    assert result.fvg_pts in [0, 7, 15]


def test_hmp_ob_points_distribution():
    """Test OB points are 0, 4, or 10."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="INACTIVE",
        regime="TREND",
    )
    result = calculate_hmp(snap, "LONG")
    
    assert result.ob_pts in [0, 4, 10]


def test_hmp_result_frozen():
    """Test that HMPResult is frozen (immutable)."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="LONDON",
        regime="TREND",
    )
    result = calculate_hmp(snap, "LONG")
    
    # Should not be able to modify frozen dataclass
    with pytest.raises(AttributeError):
        result.score = 50


def test_hmp_empty_fvg_ob_when_not_found():
    """Test that FVG and OB are None when not found."""
    m1 = OHLCV("EURUSD", "M1", 1.0850, 1.0860, 1.0845, 1.0858, 500.0, 1000)
    m3 = [
        OHLCV("EURUSD", "M3", 1.0850, 1.0860, 1.0845, 1.0858, 2000.0, 1000),
    ]
    m5 = [
        OHLCV("EURUSD", "M5", 1.0850, 1.0860, 1.0845, 1.0858, 1000.0, 1000),
    ]
    snap = MarketSnapshot(
        symbol="EURUSD",
        tick=Tick("EURUSD", 1.0855, 1.0857, 1000),
        m1=m1,
        m3=m3[-1],
        m5=m5[-1],
        cvd_history=[0.0] * 100,
        vwap=1.0850,
        atr_1m=0.0005,
        atr_5m=0.001,
        session="LONDON",
        regime="TREND",
    )
    result = calculate_hmp(snap, "LONG")
    
    # With minimal bars, might not find FVG or OB
    if not result.fvg_pts:
        assert result.fvg is None or not result.fvg.found
    if not result.ob_pts:
        assert result.order_block is None or not result.order_block.found

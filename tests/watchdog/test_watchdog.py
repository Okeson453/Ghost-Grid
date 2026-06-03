"""
tests/watchdog/test_watchdog.py
Unit tests for watchdog module.
"""

from __future__ import annotations
from dataclasses import dataclass
from watchdog.thread import WatchdogThread
from watchdog.emergency import emergency_nuclear_write


@dataclass(frozen=True)
class MockSnapshot:
    """Mock FrozenPortfolioSnapshot for testing."""
    net_equity: float
    daily_pnl: float
    day_locked: bool = False
    circuit_breaker: bool = False


def test_watchdog_initialization():
    """Test watchdog thread can be created."""
    watchdog = WatchdogThread()
    assert watchdog is not None
    assert watchdog._get_snap is None
    assert watchdog._thread is not None


def test_watchdog_set_snapshot_getter():
    """Test snapshot getter can be set."""
    watchdog = WatchdogThread()
    
    def mock_getter():
        return MockSnapshot(net_equity=10000, daily_pnl=0)
    
    watchdog.set_snapshot_getter(mock_getter)
    assert watchdog._get_snap is not None
    snap = watchdog._get_snap()
    assert snap.net_equity == 10000
    assert snap.daily_pnl == 0


def test_watchdog_poll_no_snapshot():
    """Test poll handles missing snapshot gracefully."""
    watchdog = WatchdogThread()
    # Should not raise — snapshot getter is None
    watchdog._poll()


def test_watchdog_poll_day_locked():
    """Test poll skips evaluation when day_locked."""
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: MockSnapshot(
            net_equity=10000,
            daily_pnl=-500,
            day_locked=True,
        )
    )
    # Should return early without error
    watchdog._poll()


def test_watchdog_poll_circuit_breaker():
    """Test poll skips evaluation when circuit_breaker active."""
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: MockSnapshot(
            net_equity=10000,
            daily_pnl=-500,
            circuit_breaker=True,
        )
    )
    # Should return early without error
    watchdog._poll()


def test_watchdog_poll_loss_within_limit():
    """Test poll allows loss within 4% limit."""
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: MockSnapshot(
            net_equity=10000,
            daily_pnl=-300,  # 3% loss — within 4% limit
        )
    )
    # Should complete without firing nuclear
    watchdog._poll()


def test_watchdog_poll_extreme_gain():
    """Test poll detects extreme gain but doesn't fire nuclear."""
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: MockSnapshot(
            net_equity=10000,
            daily_pnl=1800,  # 18% gain — exceeds 15% target
        )
    )
    # Should log warning but not fire emergency nuclear
    watchdog._poll()


def test_emergency_nuclear_write_no_win32():
    """Test emergency write handles missing win32."""
    # When win32 not available, should return False gracefully
    result = emergency_nuclear_write(pipe_path=r"\\.\pipe\nonexistent")
    # Result will be False if win32 not available or pipe doesn't exist
    assert isinstance(result, bool)


def test_watchdog_thread_start_stop():
    """Test watchdog thread can start and stop."""
    watchdog = WatchdogThread()
    watchdog.set_snapshot_getter(
        lambda: MockSnapshot(net_equity=10000, daily_pnl=0)
    )
    
    watchdog.start()
    # Thread should be running
    assert watchdog._thread.is_alive()
    
    watchdog.stop()
    # Thread should have stopped (within 5 second timeout)
    watchdog._thread.join(timeout=5.0)
    assert not watchdog._thread.is_alive()

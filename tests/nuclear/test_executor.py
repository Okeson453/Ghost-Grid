"""
tests/nuclear/test_executor.py
Unit tests for nuclear executor — concurrent close-all logic.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


class MockPortfolioState:
    """Mock PortfolioState for testing."""
    def __init__(self):
        self.open_positions = {
            1: MagicMock(),
            2: MagicMock(),
            3: MagicMock(),
        }
        self.realized_pnl = 100.0
        self.unrealized_pnl = -50.0


@pytest.mark.asyncio
async def test_nuclear_close_all_positions():
    """Test that all positions are closed concurrently."""
    from nuclear.executor import execute_nuclear_close
    
    state = MockPortfolioState()
    commander = AsyncMock()
    commander.close = AsyncMock(return_value=True)

    result = await execute_nuclear_close(state, commander, "LOSS_PROTECTION")

    # Should have called close for all 3 positions
    assert commander.close.call_count == 3
    assert len(result) == 3
    assert all(result.values())  # All True


@pytest.mark.asyncio
async def test_nuclear_close_no_positions():
    """Test: no open positions → return empty dict."""
    from nuclear.executor import execute_nuclear_close
    
    state = MockPortfolioState()
    state.open_positions = {}
    commander = AsyncMock()

    result = await execute_nuclear_close(state, commander, "MANUAL_TELEGRAM")

    assert result == {}
    commander.close.assert_not_called()


@pytest.mark.asyncio
async def test_nuclear_close_partial_failures():
    """Test: some close() calls fail → partial success."""
    from nuclear.executor import execute_nuclear_close
    
    state = MockPortfolioState()
    commander = AsyncMock()
    # First close succeeds, second fails, third succeeds
    commander.close = AsyncMock(side_effect=[True, False, True])

    result = await execute_nuclear_close(state, commander, "DAILY_LOSS_LIMIT")

    assert len(result) == 3
    assert sum(result.values()) == 2  # 2 successes


@pytest.mark.asyncio
async def test_nuclear_close_timeout():
    """Test: close() times out → logged as failed."""
    from nuclear.executor import execute_nuclear_close
    
    state = MockPortfolioState()
    commander = AsyncMock()
    
    # Simulate timeout by having close() never resolve
    async def slow_close(*args, **kwargs):
        await asyncio.sleep(10)  # Never completes within 3s timeout
        return True
    
    commander.close = slow_close

    result = await execute_nuclear_close(state, commander, "LATENCY_ANOMALY")

    # Should timeout and return False for all
    assert len(result) == 3
    assert all(not v for v in result.values())

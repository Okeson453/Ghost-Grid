import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from portfolio.state import PortfolioState
from telegram.commands import cmd_nuke, cmd_confirm, cmd_mode, cmd_pairs
from core.mode_selector import ModeSelector
from main import _next_position_id


@pytest.mark.asyncio
async def test_nuke_requires_confirmation_before_execution():
    mock_update = Mock()
    mock_update.effective_user.id = 42
    mock_update.effective_user.username = "ops"
    mock_update.effective_chat.id = 1001
    mock_update.message = Mock()
    mock_update.message.reply_text = AsyncMock()

    mock_ctx = Mock()
    mock_ctx.bot_data = {
        "nuclear_controller": AsyncMock(),
        "portfolio_state": PortfolioState(),
    }

    await cmd_nuke(mock_update, mock_ctx)

    assert mock_ctx.bot_data["nuclear_controller"].force_nuclear.await_count == 0
    assert any("confirm" in str(call.args[0]).lower() for call in mock_update.message.reply_text.await_args_list)

    await cmd_confirm(mock_update, mock_ctx)

    assert mock_ctx.bot_data["nuclear_controller"].force_nuclear.await_count == 1


@pytest.mark.asyncio
async def test_next_position_id_is_unique_under_concurrency():
    async def run_many():
        return [await _next_position_id() for _ in range(100)]

    ids = await asyncio.gather(*(run_many() for _ in range(5)))
    flattened = [item for batch in ids for item in batch]
    assert len(flattened) == 500
    assert len(set(flattened)) == 500


def test_mode_selector_prefers_daily_target_when_drift_is_negative():
    selector = ModeSelector()
    portfolio = PortfolioState()
    snapshot = SimpleNamespace(regime="CHOP", session="LONDON")

    mode = selector.evaluate(snapshot, portfolio)

    assert mode == "DAILY_TARGET"


def test_mode_selector_returns_scalp_burst_for_trending_market():
    selector = ModeSelector()
    portfolio = PortfolioState()
    snapshot = SimpleNamespace(regime="TREND", session="LONDON")

    mode = selector.evaluate(snapshot, portfolio)

    assert mode == "SCALP_BURST"


@pytest.mark.asyncio
async def test_mode_and_pairs_commands_render_expected_output():
    mock_update = Mock()
    mock_update.effective_user.id = 7
    mock_update.effective_user.username = "trader"
    mock_update.effective_chat.id = 1002
    mock_update.message = Mock()
    mock_update.message.reply_text = AsyncMock()

    state = PortfolioState()
    state.current_mode = "SCALP_BURST"
    ctx = Mock()
    ctx.bot_data = {"portfolio_state": state, "tracked_pairs": {"EURUSD", "GBPUSD"}}

    await cmd_mode(mock_update, ctx)
    await cmd_pairs(mock_update, ctx)

    assert mock_update.message.reply_text.await_count == 2
    assert "SCALP_BURST" in mock_update.message.reply_text.await_args_list[0].args[0]
    assert "EURUSD" in mock_update.message.reply_text.await_args_list[1].args[0]

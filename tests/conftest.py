"""
tests/conftest.py
Pytest fixtures for GHOST-GRID tests.
"""

from __future__ import annotations
import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import asyncio
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(path, name, parent):
    return None
import aiosqlite

from config import Settings
from data.schema import MarketSnapshot
from tests.fixtures import make_snapshot, make_tick_sequence


@pytest.fixture
async def in_memory_db() -> aiosqlite.Connection:
    """
    In-memory SQLite database with schema.
    Used for testing database operations without disk I/O.
    """
    # Create in-memory database
    conn = await aiosqlite.connect(":memory:")

    # Create schema tables (same as db/schema.sql)
    schema = """
    CREATE TABLE IF NOT EXISTS positions (
        position_id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_ts_ms INTEGER NOT NULL,
        entry_price REAL NOT NULL,
        lot_size REAL NOT NULL,
        stop_loss REAL NOT NULL,
        tp_price REAL,
        status TEXT DEFAULT 'OPEN'
    );

    CREATE TABLE IF NOT EXISTS fills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        fill_price REAL NOT NULL,
        fill_ts_ms INTEGER NOT NULL,
        mt5_ticket INTEGER,
        FOREIGN KEY(position_id) REFERENCES positions(position_id)
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        symbol TEXT,
        data TEXT,
        ts_ms INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        pnl_usd REAL,
        win_count INTEGER,
        loss_count INTEGER,
        max_dd REAL,
        sharpe REAL
    );
    """

    await conn.executescript(schema)
    await conn.commit()

    yield conn

    await conn.close()


@pytest.fixture
def mock_pipe_client() -> AsyncMock:
    """
    Mock PipeClient for testing without real Windows pipes.
    """
    client = AsyncMock()
    client.is_connected = True
    client.connect = AsyncMock()
    client.readline = AsyncMock(return_value=None)
    client.writeline = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_settings() -> Settings:
    """
    Sample Settings for testing.
    Uses paper trading mode and test values.
    """
    return Settings(
        telegram_token="test_token_12345",
        mt5_login="12345",
        mt5_password="password",
        mt5_server="MetaQuotes-Demo",
        pipe_path=r"\\.\pipe\ghost_grid_test",
        paper_trading=True,
        log_level="DEBUG",
        vps_timezone="UTC",
        historical_data_dir="./data_test",
    )


@pytest.fixture
def eurusd_snapshot() -> MarketSnapshot:
    """
    Pre-built EURUSD MarketSnapshot for quick testing.
    """
    return make_snapshot(
        symbol="EURUSD",
        tick_bid=1.0850,
        tick_ask=1.0851,
        session="LONDON",
        regime="TREND",
        atr_1m=0.0010,
        atr_5m=0.0015,
    )


@pytest.fixture
def tick_sequence_300() -> list:
    """
    300-tick EURUSD uptrend sequence (50ms intervals).
    Used for warmup testing in integration tests.
    """
    return make_tick_sequence(
        count=300,
        symbol="EURUSD",
        direction="up",
        interval_ms=50,
    )


@pytest.fixture
def event_loop():
    """
    Event loop fixture for async tests.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

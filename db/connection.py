"""
db/connection.py
SQLite connection pool with async interface and enterprise metrics.
WHY: Prevents connection exhaustion, centralizes pool management, enables metrics.
"""

from __future__ import annotations
import asyncio
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, AsyncGenerator

from config import get_settings


def _dict_factory(cursor, row):
    """Factory to return rows as dicts."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


@dataclass
class ConnectionMetrics:
    """Metrics for SQLite connection pool."""

    connections_created: int = 0
    connections_closed: int = 0
    transactions_active: int = 0
    pool_exhaustion_events: int = 0
    connection_errors: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.connections_created = 0
        self.connections_closed = 0
        self.transactions_active = 0
        self.pool_exhaustion_events = 0
        self.connection_errors = 0


class ConnectionPool:
    """
    Async SQLite connection pool.
    WHY: SQLite doesn't support true connection pooling (single writer).
    This implements a queue-based pool to prevent connection thrashing.
    """

    def __init__(
        self,
        db_path: str,
        pool_size: int = 5,
    ):
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._pool: asyncio.Queue[sqlite3.Connection] = asyncio.Queue(maxsize=pool_size)
        self._metrics = ConnectionMetrics()
        self._initialized = False

    async def init(self) -> None:
        """Initialize connection pool (pre-populate with connections)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        for _ in range(self.pool_size):
            try:
                conn = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,
                    timeout=10.0,
                )
                conn.row_factory = _dict_factory
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA foreign_keys=ON")
                await self._pool.put(conn)
                self._metrics.connections_created += 1
            except sqlite3.Error as e:
                self._metrics.connection_errors += 1
                raise RuntimeError(f"Failed to initialize connection: {e}")

        self._initialized = True

    async def acquire(self) -> sqlite3.Connection:
        """
        Acquire a connection from the pool.
        WHY: Queue ensures we never exceed pool_size active connections.
        """
        if not self._initialized:
            await self.init()

        try:
            conn = self._pool.get_nowait()
            self._metrics.transactions_active += 1
            return conn
        except asyncio.QueueEmpty:
            self._metrics.pool_exhaustion_events += 1
            # Wait up to 30s for a connection to be returned
            try:
                conn = await asyncio.wait_for(self._pool.get(), timeout=30.0)
                self._metrics.transactions_active += 1
                return conn
            except asyncio.TimeoutError as e:
                self._metrics.connection_errors += 1
                raise RuntimeError("Connection pool exhausted after 30s") from e

    async def release(self, conn: sqlite3.Connection) -> None:
        """Return connection to pool."""
        self._metrics.transactions_active = max(
            0, self._metrics.transactions_active - 1
        )
        await self._pool.put(conn)

    async def close_all(self) -> None:
        """Close all pooled connections."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
                self._metrics.connections_closed += 1
            except asyncio.QueueEmpty:
                break

    @property
    def metrics(self) -> ConnectionMetrics:
        """Expose metrics."""
        return self._metrics


# ──────────────────────────────────────────────────────────────────────────────
# Global pool singleton
# ──────────────────────────────────────────────────────────────────────────────
_pool: Optional[ConnectionPool] = None


async def get_pool() -> ConnectionPool:
    """
    Get or create the global connection pool.
    WHY: Singleton ensures only one pool per process.
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(db_path=settings.db_path, pool_size=5)
        await _pool.init()
    return _pool


async def get_async_connection() -> sqlite3.Connection:
    """
    Backwards-compatible helper: acquire a single connection from the global pool.
    Returns a sqlite3.Connection instance.
    """
    pool = await get_pool()
    conn = await pool.acquire()
    return conn


async def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Minimal migration runner to create required tables if they don't exist.
    This is intentionally simple to allow `main.py` startup during testing.
    """
    try:
        cursor = conn.cursor()
        # Positions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                state TEXT,
                entry_price REAL,
                entry_time_utc TEXT,
                entry_bar_id INTEGER,
                entry_session TEXT,
                lot_size REAL,
                pip_size REAL,
                pip_value REAL,
                h_c_entry INTEGER,
                regime_entry TEXT,
                confluence_score INTEGER,
                risk_usd REAL,
                exit_price REAL,
                exit_time_utc TEXT,
                exit_bar_id INTEGER,
                exit_session TEXT,
                exit_reason TEXT,
                pnl_usd REAL,
                pnl_pips REAL
            )
            """
        )

        # Signals, regimes, snapshots minimal tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                signal_type TEXT,
                bar_id INTEGER,
                signal_time_utc TEXT,
                session TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS regimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                regime TEXT,
                start_time_utc TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp_ms INTEGER,
                data TEXT
            )
            """
        )

        conn.commit()
    except Exception as e:
        raise RuntimeError(f"Failed to run migrations: {e}")

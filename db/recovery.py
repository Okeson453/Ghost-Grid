"""
db/recovery.py
Crash recovery: rebuild system state from database on reconnect.
WHY: Enables graceful recovery without data loss or position duplication.
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import Optional

from .connection import get_pool
from .reader import DatabaseReader


@dataclass
class RecoveryMetrics:
    """Metrics for recovery operations."""

    recovery_events: int = 0
    positions_recovered: int = 0
    signals_recovered: int = 0
    regimes_recovered: int = 0
    recovery_errors: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.recovery_events = 0
        self.positions_recovered = 0
        self.signals_recovered = 0
        self.regimes_recovered = 0
        self.recovery_errors = 0


class DatabaseRecovery:
    """
    Crash recovery: rebuild state from persistent database.
    WHY: On reconnect, system needs to know which positions are active.
    """

    def __init__(self, reader: DatabaseReader):
        self.reader = reader
        self._metrics = RecoveryMetrics()

    async def recover_state(self) -> dict:
        """
        Recover system state from database after crash/disconnect.
        Returns: {
            'open_positions': [...],
            'recent_signals': {...},
            'regimes': {...},
            'recovery_time_utc': '...'
        }
        """
        try:
            self._metrics.recovery_events += 1

            # Get all open positions across all symbols
            open_positions = await self.reader.get_open_positions()
            self._metrics.positions_recovered = len(open_positions)

            # Get position statistics
            stats = await self.reader.get_position_stats()

            # Group open positions by symbol
            positions_by_symbol = {}
            for pos in open_positions:
                symbol = pos["symbol"]
                if symbol not in positions_by_symbol:
                    positions_by_symbol[symbol] = []
                positions_by_symbol[symbol].append(pos)

            return {
                "open_positions": open_positions,
                "positions_by_symbol": positions_by_symbol,
                "position_count": len(open_positions),
                "position_stats": stats,
                "recovery_event_count": self._metrics.recovery_events,
            }

        except Exception as e:
            self._metrics.recovery_errors += 1
            raise RuntimeError(f"Failed to recover state: {e}")

    async def get_open_positions_for_symbol(self, symbol: str) -> list[dict]:
        """Get all open positions for a specific symbol."""
        try:
            pool = await get_pool()
            conn = await pool.acquire()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM positions WHERE state = 'OPEN' AND symbol = ?",
                    (symbol,),
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                await pool.release(conn)

        except sqlite3.Error as e:
            self._metrics.recovery_errors += 1
            raise RuntimeError(f"Failed to get open positions for {symbol}: {e}")

    async def verify_database_integrity(self) -> bool:
        """
        Verify database integrity: check for corruption, run PRAGMA checks.
        WHY: Early detection prevents data corruption from persisting.
        """
        try:
            pool = await get_pool()
            conn = await pool.acquire()
            try:
                cursor = conn.cursor()

                # PRAGMA integrity_check
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()

                if result[0] != "ok":
                    self._metrics.recovery_errors += 1
                    raise RuntimeError(f"Database integrity check failed: {result[0]}")

                # Verify all required tables exist
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN (
                        'positions', 'signals', 'regimes', 'snapshots'
                    )
                    """
                )
                tables = {row[0] for row in cursor.fetchall()}
                required = {"positions", "signals", "regimes", "snapshots"}

                if not required.issubset(tables):
                    missing = required - tables
                    raise RuntimeError(f"Missing required tables: {missing}")

                return True

            finally:
                await pool.release(conn)

        except Exception as e:
            self._metrics.recovery_errors += 1
            raise RuntimeError(f"Database integrity verification failed: {e}")


async def get_open_positions_from_db() -> list[dict]:
    """Compatibility helper: return list of open positions from DB."""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE state = 'OPEN'")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await pool.release(conn)


async def get_next_position_id() -> int:
    """Return next available sequential position id (max(id)+1)."""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) as max_id FROM positions")
        row = cursor.fetchone()
        if not row:
            return 1
        # row may be a dict (row_factory) or tuple
        if isinstance(row, dict):
            max_id = row.get("max_id")
        else:
            max_id = row[0]
        if max_id is None:
            return 1
        return int(max_id) + 1
    finally:
        await pool.release(conn)

    async def compact_database(self) -> bool:
        """
        Compact database (VACUUM) to reclaim space.
        WHY: Regular VACUUMs prevent unbounded growth after deletions/updates.
        """
        try:
            pool = await get_pool()
            conn = await pool.acquire()
            try:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                conn.commit()
                return True
            finally:
                await pool.release(conn)

        except sqlite3.Error as e:
            self._metrics.recovery_errors += 1
            raise RuntimeError(f"Failed to compact database: {e}")

    async def get_recovery_summary(self) -> dict:
        """Get summary of last recovery operation."""
        try:
            pool = await get_pool()
            conn = await pool.acquire()
            try:
                cursor = conn.cursor()

                # Count records by table
                cursor.execute("SELECT COUNT(*) FROM positions WHERE state = 'OPEN'")
                open_pos = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM positions WHERE state = 'CLOSED'")
                closed_pos = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM signals")
                signal_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM regimes")
                regime_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM snapshots")
                snapshot_count = cursor.fetchone()[0]

                return {
                    "open_positions": open_pos,
                    "closed_positions": closed_pos,
                    "signals": signal_count,
                    "regimes": regime_count,
                    "snapshots": snapshot_count,
                    "total_records": open_pos
                    + closed_pos
                    + signal_count
                    + regime_count
                    + snapshot_count,
                }

            finally:
                await pool.release(conn)

        except Exception as e:
            self._metrics.recovery_errors += 1
            raise RuntimeError(f"Failed to get recovery summary: {e}")

    @property
    def metrics(self) -> RecoveryMetrics:
        """Expose metrics."""
        return self._metrics

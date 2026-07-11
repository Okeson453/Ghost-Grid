"""
db/reader.py
Query interface for reading positions, signals, regimes from database.
WHY: Enables recovery, position validation, and analytics queries.
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, Any

from .connection import get_pool


@dataclass
class ReaderMetrics:
    """Metrics for database read operations."""

    queries_executed: int = 0
    rows_read: int = 0
    query_errors: int = 0
    position_queries: int = 0
    signal_queries: int = 0
    regime_queries: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.queries_executed = 0
        self.rows_read = 0
        self.query_errors = 0
        self.position_queries = 0
        self.signal_queries = 0
        self.regime_queries = 0


class DatabaseReader:
    """
    Query interface for GHOST-GRID domain objects.
    WHY: Read-heavy access patterns (recovery, validation, analytics).
    """

    def __init__(self):
        self._metrics = ReaderMetrics()

    async def get_open_positions(self, symbol: Optional[str] = None) -> list[dict]:
        """Get all open positions, optionally filtered by symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.position_queries += 1
            cursor = conn.cursor()

            if symbol:
                cursor.execute(
                    "SELECT * FROM positions WHERE state = 'OPEN' AND symbol = ?",
                    (symbol,),
                )
            else:
                cursor.execute("SELECT * FROM positions WHERE state = 'OPEN'")

            rows = cursor.fetchall()
            self._metrics.rows_read += len(rows)
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query open positions: {e}")
        finally:
            await pool.release(conn)

    async def get_closed_positions(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> list[dict]:
        """Get closed positions, optionally filtered by symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.position_queries += 1
            cursor = conn.cursor()

            if symbol:
                cursor.execute(
                    """
                    SELECT * FROM positions
                    WHERE state = 'CLOSED' AND symbol = ?
                    ORDER BY exit_time_utc DESC
                    LIMIT ?
                    """,
                    (symbol, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM positions
                    WHERE state = 'CLOSED'
                    ORDER BY exit_time_utc DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            self._metrics.rows_read += len(rows)
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query closed positions: {e}")
        finally:
            await pool.release(conn)

    async def get_position_by_id(self, position_id: int) -> Optional[dict]:
        """Get a single position by ID."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.position_queries += 1
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
            row = cursor.fetchone()
            if row:
                self._metrics.rows_read += 1
                return dict(row)
            return None

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query position: {e}")
        finally:
            await pool.release(conn)

    async def get_recent_signals(self, symbol: str, limit: int = 50) -> list[dict]:
        """Get recent signals for a symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.signal_queries += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM signals
                WHERE symbol = ?
                ORDER BY signal_time_utc DESC
                LIMIT ?
                """,
                (symbol, limit),
            )

            rows = cursor.fetchall()
            self._metrics.rows_read += len(rows)
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query signals: {e}")
        finally:
            await pool.release(conn)

    async def get_signals_by_type(
        self, symbol: str, signal_type: str, limit: int = 50
    ) -> list[dict]:
        """Get signals by type for a symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.signal_queries += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM signals
                WHERE symbol = ? AND signal_type = ?
                ORDER BY signal_time_utc DESC
                LIMIT ?
                """,
                (symbol, signal_type, limit),
            )

            rows = cursor.fetchall()
            self._metrics.rows_read += len(rows)
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query signals: {e}")
        finally:
            await pool.release(conn)

    async def get_current_regime(self, symbol: str) -> Optional[dict]:
        """Get the most recent regime for a symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.regime_queries += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM regimes
                WHERE symbol = ? AND end_time_utc IS NULL
                ORDER BY start_time_utc DESC
                LIMIT 1
                """,
                (symbol,),
            )

            row = cursor.fetchone()
            if row:
                self._metrics.rows_read += 1
                return dict(row)
            return None

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query regime: {e}")
        finally:
            await pool.release(conn)

    async def get_regime_history(self, symbol: str, limit: int = 50) -> list[dict]:
        """Get regime history for a symbol."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.regime_queries += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM regimes
                WHERE symbol = ?
                ORDER BY start_time_utc DESC
                LIMIT ?
                """,
                (symbol, limit),
            )

            rows = cursor.fetchall()
            self._metrics.rows_read += len(rows)
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query regime history: {e}")
        finally:
            await pool.release(conn)

    async def get_position_stats(self, symbol: Optional[str] = None) -> dict:
        """Get position statistics: win rate, avg profit, etc."""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.queries_executed += 1
            self._metrics.position_queries += 1
            cursor = conn.cursor()

            where_clause = "WHERE symbol = ?" if symbol else ""
            params = (symbol,) if symbol else ()

            cursor.execute(
                f"""
                SELECT
                    COUNT(*) as total_closed,
                    COUNT(CASE WHEN pnl_usd > 0 THEN 1 END) as wins,
                    COUNT(CASE WHEN pnl_usd < 0 THEN 1 END) as losses,
                    ROUND(AVG(pnl_usd), 2) as avg_pnl_usd,
                    ROUND(SUM(pnl_usd), 2) as total_pnl_usd,
                    ROUND(SUM(pnl_pips), 2) as total_pnl_pips,
                    MIN(pnl_usd) as worst_loss,
                    MAX(pnl_usd) as best_win
                FROM positions
                WHERE state = 'CLOSED' {where_clause}
                """,
                params,
            )

            row = cursor.fetchone()
            if row:
                self._metrics.rows_read += 1
                stats = dict(row)
                # Calculate win rate
                total = stats["total_closed"]
                if total > 0:
                    stats["win_rate"] = round(stats["wins"] / total * 100, 2)
                else:
                    stats["win_rate"] = 0.0
                return stats
            return {}

        except sqlite3.Error as e:
            self._metrics.query_errors += 1
            raise RuntimeError(f"Failed to query position stats: {e}")
        finally:
            await pool.release(conn)

    @property
    def metrics(self) -> ReaderMetrics:
        """Expose metrics."""
        return self._metrics

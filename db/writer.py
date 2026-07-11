"""
db/writer.py
Append-only transaction writer with enterprise metrics.
WHY: Enables reliable position/signal/regime recording with observability.
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .connection import get_pool


@dataclass
class WriterMetrics:
    """Metrics for database write operations."""

    positions_written: int = 0
    signals_written: int = 0
    regimes_written: int = 0
    snapshots_written: int = 0
    total_transactions: int = 0
    write_errors: int = 0
    batch_operations: int = 0

    def reset(self) -> None:
        """Reset all counters for testing."""
        self.positions_written = 0
        self.signals_written = 0
        self.regimes_written = 0
        self.snapshots_written = 0
        self.total_transactions = 0
        self.write_errors = 0
        self.batch_operations = 0


class DatabaseWriter:
    """
    Append-only writer for GHOST-GRID domain objects.
    WHY: Atomic transactions + metrics enable crash recovery and auditing.
    """

    def __init__(self):
        self._metrics = WriterMetrics()

    async def write_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_time_utc: str,
        entry_bar_id: int,
        entry_session: str,
        lot_size: float,
        pip_size: float,
        pip_value: float,
        h_c_entry: int,
        regime_entry: str,
        confluence_score: Optional[int] = None,
        risk_usd: Optional[float] = None,
        exit_price: Optional[float] = None,
        exit_time_utc: Optional[str] = None,
        exit_bar_id: Optional[int] = None,
        exit_session: Optional[str] = None,
        exit_reason: Optional[str] = None,
        pnl_usd: Optional[float] = None,
        pnl_pips: Optional[float] = None,
    ) -> int:
        """
        Write a position to database.
        Returns: position_id
        """
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.total_transactions += 1
            cursor = conn.cursor()

            # Determine state based on exit_price
            state = "CLOSED" if exit_price is not None else "OPEN"

            cursor.execute(
                """
                INSERT INTO positions (
                    symbol, direction, state,
                    entry_price, entry_time_utc, entry_bar_id, entry_session,
                    lot_size, pip_size, pip_value,
                    h_c_entry, regime_entry, confluence_score, risk_usd,
                    exit_price, exit_time_utc, exit_bar_id, exit_session,
                    exit_reason, pnl_usd, pnl_pips
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    direction,
                    state,
                    entry_price,
                    entry_time_utc,
                    entry_bar_id,
                    entry_session,
                    lot_size,
                    pip_size,
                    pip_value,
                    h_c_entry,
                    regime_entry,
                    confluence_score,
                    risk_usd,
                    exit_price,
                    exit_time_utc,
                    exit_bar_id,
                    exit_session,
                    exit_reason,
                    pnl_usd,
                    pnl_pips,
                ),
            )
            conn.commit()
            self._metrics.positions_written += 1
            position_id = cursor.lastrowid
            return position_id

        except sqlite3.Error as e:
            self._metrics.write_errors += 1
            raise RuntimeError(f"Failed to write position: {e}")
        finally:
            await pool.release(conn)

    async def write_signal(
        self,
        symbol: str,
        signal_type: str,
        bar_id: int,
        signal_time_utc: str,
        session: str,
        h_c_value: Optional[int] = None,
        regime_from: Optional[str] = None,
        regime_to: Optional[str] = None,
        cvd_zscore: Optional[float] = None,
        confluence_count: Optional[int] = None,
        severity: Optional[str] = None,
    ) -> int:
        """Write a signal to database. Returns: signal_id"""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.total_transactions += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO signals (
                    symbol, signal_type, bar_id, signal_time_utc, session,
                    h_c_value, regime_from, regime_to, cvd_zscore,
                    confluence_count, severity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    signal_type,
                    bar_id,
                    signal_time_utc,
                    session,
                    h_c_value,
                    regime_from,
                    regime_to,
                    cvd_zscore,
                    confluence_count,
                    severity,
                ),
            )
            conn.commit()
            self._metrics.signals_written += 1
            signal_id = cursor.lastrowid
            return signal_id

        except sqlite3.Error as e:
            self._metrics.write_errors += 1
            raise RuntimeError(f"Failed to write signal: {e}")
        finally:
            await pool.release(conn)

    async def write_regime(
        self,
        symbol: str,
        regime: str,
        bar_id: int,
        start_time_utc: str,
        session: str,
        regime_strength: Optional[int] = None,
        h_c_height: Optional[int] = None,
    ) -> int:
        """Write a regime to database. Returns: regime_id"""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.total_transactions += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO regimes (
                    symbol, regime, bar_id, start_time_utc, session,
                    regime_strength, h_c_height
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    regime,
                    bar_id,
                    start_time_utc,
                    session,
                    regime_strength,
                    h_c_height,
                ),
            )
            conn.commit()
            self._metrics.regimes_written += 1
            regime_id = cursor.lastrowid
            return regime_id

        except sqlite3.Error as e:
            self._metrics.write_errors += 1
            raise RuntimeError(f"Failed to write regime: {e}")
        finally:
            await pool.release(conn)

    async def write_snapshot(
        self,
        symbol: str,
        bar_id: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        vwap: float,
        atr: float,
        atr_1m: float,
        cvd_value: float,
        cvd_zscore: float,
        snapshot_time_utc: str,
        session: str,
        h_c_value: Optional[int] = None,
        regime: Optional[str] = None,
    ) -> int:
        """Write a snapshot to database. Returns: snapshot_id"""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.total_transactions += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO snapshots (
                    symbol, bar_id, open, high, low, close, volume,
                    vwap, atr, atr_1m, cvd_value, cvd_zscore,
                    h_c_value, regime, snapshot_time_utc, session
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    bar_id,
                    open_price,
                    high,
                    low,
                    close,
                    volume,
                    vwap,
                    atr,
                    atr_1m,
                    cvd_value,
                    cvd_zscore,
                    h_c_value,
                    regime,
                    snapshot_time_utc,
                    session,
                ),
            )
            conn.commit()
            self._metrics.snapshots_written += 1
            snapshot_id = cursor.lastrowid
            return snapshot_id

        except sqlite3.Error as e:
            self._metrics.write_errors += 1
            raise RuntimeError(f"Failed to write snapshot: {e}")
        finally:
            await pool.release(conn)

    async def update_position_exit(
        self,
        position_id: int,
        exit_price: float,
        exit_time_utc: str,
        exit_bar_id: int,
        exit_session: str,
        exit_reason: str,
        pnl_usd: float,
        pnl_pips: float,
    ) -> bool:
        """Update position with exit data. Returns: success"""
        pool = await get_pool()
        conn = await pool.acquire()
        try:
            self._metrics.total_transactions += 1
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE positions
                SET state = 'CLOSED',
                    exit_price = ?, exit_time_utc = ?, exit_bar_id = ?,
                    exit_session = ?, exit_reason = ?, pnl_usd = ?, pnl_pips = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    exit_price,
                    exit_time_utc,
                    exit_bar_id,
                    exit_session,
                    exit_reason,
                    pnl_usd,
                    pnl_pips,
                    position_id,
                ),
            )
            conn.commit()
            rows_affected = cursor.rowcount
            return rows_affected > 0

        except sqlite3.Error as e:
            self._metrics.write_errors += 1
            raise RuntimeError(f"Failed to update position exit: {e}")
        finally:
            await pool.release(conn)

    @property
    def metrics(self) -> WriterMetrics:
        """Expose metrics."""
        return self._metrics


# ──────────────────────────────────────────────────────────────────────────────
# Module-level convenience functions for common write operations
# ──────────────────────────────────────────────────────────────────────────────

_writer_instance: Optional[DatabaseWriter] = None


def get_writer() -> DatabaseWriter:
    """Get or create the global DatabaseWriter instance."""
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = DatabaseWriter()
    return _writer_instance


async def write_position_opened(
    position_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    lot_size: float,
    leverage: float,
    hc_score: int,
    regime: str,
    session: str,
    mt5_ticket: Optional[int] = None,
    open_ts: Optional[int] = None,
) -> int:
    """
    Convenience function to record a position opening.
    This captures the entry point and confluence data.
    """
    writer = get_writer()

    # Convert timestamp to ISO format if provided
    entry_time_utc = (
        datetime.fromtimestamp(open_ts / 1000.0, tz=timezone.utc).isoformat()
        if open_ts
        else datetime.now(timezone.utc).isoformat()
    )

    # Calculate pip size from common forex patterns
    # This is simplified; real implementation should look up from config/instruments.py
    pip_size = 0.0001 if "JPY" not in symbol else 0.01
    pip_value = 10.0 if "JPY" not in symbol else 9.09

    # Calculate risk in USD
    risk_usd = abs(entry_price - stop_loss) * (lot_size * 100000) * pip_value

    # For opening, we don't have exit data yet; bar_id is set to 0
    return await writer.write_position(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        entry_time_utc=entry_time_utc,
        entry_bar_id=0,  # Will be updated from MT5
        entry_session=session,
        lot_size=lot_size,
        pip_size=pip_size,
        pip_value=pip_value,
        h_c_entry=hc_score,
        regime_entry=regime,
        confluence_score=hc_score,
        risk_usd=risk_usd,
        exit_price=None,
        exit_time_utc=None,
        exit_bar_id=None,
        exit_session=None,
        exit_reason=None,
        pnl_usd=None,
        pnl_pips=None,
    )


async def write_h_score(
    symbol: str,
    bar_id: int,
    signal_time_utc: str,
    session: str,
    h_c_value: int,
    regime: str,
    confluence_count: int,
    direction: str,
) -> int:
    """
    Convenience function to record H_c confluence scoring signal.
    """
    writer = get_writer()
    return await writer.write_signal(
        symbol=symbol,
        signal_type="CONFLUENCE",
        bar_id=bar_id,
        signal_time_utc=signal_time_utc,
        session=session,
        h_c_value=h_c_value,
        regime_from=regime,
        regime_to=regime,
        cvd_zscore=None,
        confluence_count=confluence_count,
        severity=direction.upper(),
    )

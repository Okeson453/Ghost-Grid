"""
security/audit_log.py
Audit logging for manual commands (/nuke, /pause, /resume, etc.).

Maintains immutable audit trail in SQLite for compliance and debugging.
All manual overrides are logged with timestamp, operator ID, and command.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
import sqlite3

if TYPE_CHECKING:
    from db.connection import ConnectionPool

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Manual command actions."""

    NUKE = "NUKE"  # Manual nuclear exit
    PAUSE = "PAUSE"  # Halt trading
    RESUME = "RESUME"  # Resume trading
    MODSTOP = "MODSTOP"  # Modify stop loss (if added later)
    CONFIG_CHANGE = "CONFIG_CHANGE"  # Risk constant modification (if attempted)


class AuditLogEntry:
    """Single audit log entry."""

    def __init__(
        self,
        action: AuditAction,
        operator_id: str,  # Telegram user ID
        details: str,  # JSON or description
        timestamp_utc: Optional[datetime] = None,
    ):
        self.action = action
        self.operator_id = operator_id
        self.details = details
        self.timestamp_utc = timestamp_utc or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert to dict for database storage."""
        return {
            "action": self.action.value,
            "operator_id": self.operator_id,
            "details": self.details,
            "timestamp_utc": self.timestamp_utc.isoformat(),
        }


async def init_audit_table(conn: sqlite3.Connection) -> None:
    """Create audit_log table if it doesn't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                details TEXT,
                timestamp_utc TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp_utc)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_log(operator_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)"
        )
        conn.commit()
        logger.info("Audit log table initialized")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize audit log table: {e}")
        raise


async def log_action(
    pool: "ConnectionPool",
    action: AuditAction,
    operator_id: str,
    details: str = "",
) -> None:
    """
    Log a manual command to the audit trail.

    Args:
        pool:         ConnectionPool instance
        action:       AuditAction enum (NUKE, PAUSE, RESUME, etc.)
        operator_id:  Telegram user ID or operator identifier
        details:      JSON or description of the action

    Never raises — logs errors and continues.
    """
    try:
        conn = await pool.acquire()
        try:
            entry = AuditLogEntry(action, operator_id, details)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (action, operator_id, details, timestamp_utc)
                VALUES (?, ?, ?, ?)
                """,
                (entry.action.value, entry.operator_id, entry.details, entry.timestamp_utc.isoformat()),
            )
            conn.commit()
            logger.info(
                f"Audit log: {action.value} by {operator_id} — {details[:50]}"
            )
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Audit logging failed: {e}")
        # Don't raise — audit failure should not block operation


async def get_audit_log(
    pool: "ConnectionPool",
    action: Optional[AuditAction] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Retrieve audit log entries.

    Args:
        pool:   ConnectionPool instance
        action: Filter by action (None = all)
        limit:  Maximum entries to return

    Returns:
        List of audit log dicts, most recent first.
    """
    try:
        conn = await pool.acquire()
        try:
            cursor = conn.cursor()
            if action:
                cursor.execute(
                    """
                    SELECT id, action, operator_id, details, timestamp_utc
                    FROM audit_log
                    WHERE action = ?
                    ORDER BY timestamp_utc DESC
                    LIMIT ?
                    """,
                    (action.value, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, action, operator_id, details, timestamp_utc
                    FROM audit_log
                    ORDER BY timestamp_utc DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Failed to retrieve audit log: {e}")
        return []

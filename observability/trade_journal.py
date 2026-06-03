"""
observability/trade_journal.py
Per-trade record CSV journal.

Appends rows to ./data_store/trades.csv on position open and close.
Columns: position_id, symbol, direction, entry_price, stop_loss, lot_size,
         entry_time_utc, entry_h_c, entry_regime, entry_session,
         exit_time_utc, exit_price, exit_reason, pnl_usd, pnl_pct, duration_min

WHY: complete post-trade record for analysis, walk-forward validation,
and trader review. Integrates with DriftDetector.
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional


class TradeJournal:
    """
    Append-only CSV journal of all opened and closed trades.
    One row per closed position with full entry/exit metadata.
    """

    def __init__(self, csv_path: Optional[str] = None) -> None:
        if csv_path is None:
            csv_path = "./data_store/trades.csv"
        self.csv_path = Path(csv_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create CSV with headers if it doesn't exist."""
        if self.csv_path.exists():
            return

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "position_id",
            "symbol",
            "direction",
            "entry_price",
            "stop_loss",
            "lot_size",
            "entry_time_utc",
            "entry_h_c",
            "entry_regime",
            "entry_session",
            "exit_time_utc",
            "exit_price",
            "exit_reason",
            "pnl_usd",
            "pnl_pct",
            "duration_min",
            "max_profit_usd",
            "max_loss_usd",
            "layers_closed",
        ]

        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

    def record_opened(
        self,
        position_id: int,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        lot_size: float,
        entry_h_c: int,
        entry_regime: str,
        entry_session: str,
        entry_time_utc_ms: int,
    ) -> None:
        """
        Record position open event.
        This is a partial row — closed fields will be filled on close.
        """
        entry_time_utc = (
            datetime.utcfromtimestamp(entry_time_utc_ms / 1000.0).isoformat() + "Z"
        )

        row = {
            "position_id": position_id,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "lot_size": lot_size,
            "entry_time_utc": entry_time_utc,
            "entry_h_c": entry_h_c,
            "entry_regime": entry_regime,
            "entry_session": entry_session,
            "exit_time_utc": "",
            "exit_price": "",
            "exit_reason": "",
            "pnl_usd": "",
            "pnl_pct": "",
            "duration_min": "",
            "max_profit_usd": "",
            "max_loss_usd": "",
            "layers_closed": "",
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

    def record_closed(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str,
        pnl_usd: float,
        pnl_pct: float,
        exit_time_utc_ms: int,
        entry_time_utc_ms: int,
        max_profit_usd: float = 0.0,
        max_loss_usd: float = 0.0,
        layers_closed: int = 1,
    ) -> None:
        """
        Record position close event.
        This appends a new row with the closing fields filled.

        Args:
            position_id: Position ID for correlation
            exit_price: Exit fill price
            exit_reason: ExitReason enum value (str)
            pnl_usd: Realized profit/loss in USD
            pnl_pct: P&L as % of entry risk
            exit_time_utc_ms: Exit timestamp in milliseconds
            entry_time_utc_ms: Entry timestamp in milliseconds (for duration calc)
            max_profit_usd: Peak profit during position
            max_loss_usd: Peak loss during position
            layers_closed: Number of layers closed (1–4)
        """
        exit_time_utc = (
            datetime.utcfromtimestamp(exit_time_utc_ms / 1000.0).isoformat() + "Z"
        )
        entry_time_utc = (
            datetime.utcfromtimestamp(entry_time_utc_ms / 1000.0).isoformat() + "Z"
        )

        duration_min = (exit_time_utc_ms - entry_time_utc_ms) / (1000 * 60)

        row = {
            "position_id": position_id,
            "symbol": "",  # Will be matched from open record
            "direction": "",
            "entry_price": "",
            "stop_loss": "",
            "lot_size": "",
            "entry_time_utc": entry_time_utc,
            "entry_h_c": "",
            "entry_regime": "",
            "entry_session": "",
            "exit_time_utc": exit_time_utc,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "duration_min": duration_min,
            "max_profit_usd": max_profit_usd,
            "max_loss_usd": max_loss_usd,
            "layers_closed": layers_closed,
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)


# ── Global singleton instance ──────────────────────────────────────────

_journal: Optional[TradeJournal] = None


def get_journal() -> TradeJournal:
    """Get or create the global TradeJournal instance."""
    global _journal
    if _journal is None:
        _journal = TradeJournal()
    return _journal


def record_trade_opened(
    position_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    lot_size: float,
    entry_h_c: int,
    entry_regime: str,
    entry_session: str,
    entry_time_utc_ms: int,
) -> None:
    """Record trade opened. Convenience wrapper."""
    get_journal().record_opened(
        position_id,
        symbol,
        direction,
        entry_price,
        stop_loss,
        lot_size,
        entry_h_c,
        entry_regime,
        entry_session,
        entry_time_utc_ms,
    )


def record_trade_closed(
    position_id: int,
    exit_price: float,
    exit_reason: str,
    pnl_usd: float,
    pnl_pct: float,
    exit_time_utc_ms: int,
    entry_time_utc_ms: int,
    max_profit_usd: float = 0.0,
    max_loss_usd: float = 0.0,
    layers_closed: int = 1,
) -> None:
    """Record trade closed. Convenience wrapper."""
    get_journal().record_closed(
        position_id,
        exit_price,
        exit_reason,
        pnl_usd,
        pnl_pct,
        exit_time_utc_ms,
        entry_time_utc_ms,
        max_profit_usd,
        max_loss_usd,
        layers_closed,
    )

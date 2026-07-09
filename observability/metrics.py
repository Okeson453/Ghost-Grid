"""
observability/metrics.py
CSV metrics collector — H_c scores, fills, and latency tracking.

Appends rows to ./data_store/metrics.csv every scoring cycle.
Columns: timestamp_ms, symbol, h_c_hmp, h_c_hlcp, h_c_mpp, composite, direction,
         regime, session, gate_decision, fill_latency_ms

WHY: post-session analysis of signal distribution, regime alignment,
and execution latency. Enables statistical drift detection.
"""

from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional
from scoring.models import ConfluenceScore, GateDecision


class MetricsCollector:
    """
    Singleton CSV appender for H_c scores and execution metrics.
    Thread-safe append-only design.
    """

    def __init__(self, csv_path: Optional[str] = None) -> None:
        if csv_path is None:
            csv_path = "./data_store/metrics.csv"
        self.csv_path = Path(csv_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Create CSV with headers if it doesn't exist."""
        if self.csv_path.exists():
            return

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "timestamp_ms",
            "utc_datetime",
            "symbol",
            "hmp_score",
            "hlcp_score",
            "mpp_score",
            "composite_score",
            "direction",
            "regime",
            "session",
            "gate_decision",
            "fill_latency_ms",
            "notes",
        ]

        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

    def record_score(
        self,
        score: ConfluenceScore,
        gate_decision: str = "",
    ) -> None:
        """
        Record a confluence score to CSV.
        Args:
            score: ConfluenceScore from scoring/fusion.py
            gate_decision: GateDecision result (str)
        """
        utc_dt = datetime.utcfromtimestamp(score.timestamp_ms / 1000.0)
        utc_datetime = utc_dt.isoformat() + "Z"

        row = {
            "timestamp_ms": score.timestamp_ms,
            "utc_datetime": utc_datetime,
            "symbol": score.symbol,
            "hmp_score": score.hmp,
            "hlcp_score": score.hlcp,
            "mpp_score": score.mpp,
            "composite_score": score.composite,
            "direction": score.direction,
            "regime": score.regime,
            "session": score.session,
            "gate_decision": gate_decision,
            "fill_latency_ms": "",
            "notes": "",
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

    def record_fill(
        self,
        symbol: str,
        position_id: int,
        latency_ms: float,
        fill_price: float,
        lot_size: float,
    ) -> None:
        """
        Record an order fill event with latency.
        Args:
            symbol: Instrument symbol
            position_id: Position ID
            latency_ms: Signal-to-fill latency in milliseconds
            fill_price: Executed fill price
            lot_size: Filled lot size
        """
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        utc_dt = datetime.utcfromtimestamp(now_ms / 1000.0)
        utc_datetime = utc_dt.isoformat() + "Z"

        row = {
            "timestamp_ms": now_ms,
            "utc_datetime": utc_datetime,
            "symbol": symbol,
            "hmp_score": "",
            "hlcp_score": "",
            "mpp_score": "",
            "composite_score": "",
            "direction": "",
            "regime": "",
            "session": "",
            "gate_decision": "",
            "fill_latency_ms": latency_ms,
            "notes": f"POS#{position_id} @{fill_price:.5f} x{lot_size}",
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

    def record_latency(
        self,
        symbol: str,
        latency_ms: float,
        event_type: str = "tick_to_signal",
    ) -> None:
        """
        Record a latency measurement.
        Args:
            symbol: Instrument symbol
            latency_ms: Latency in milliseconds
            event_type: Type of latency (e.g., "tick_to_signal", "signal_to_fill")
        """
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        utc_dt = datetime.utcfromtimestamp(now_ms / 1000.0)
        utc_datetime = utc_dt.isoformat() + "Z"

        row = {
            "timestamp_ms": now_ms,
            "utc_datetime": utc_datetime,
            "symbol": symbol,
            "hmp_score": "",
            "hlcp_score": "",
            "mpp_score": "",
            "composite_score": "",
            "direction": "",
            "regime": "",
            "session": "",
            "gate_decision": "",
            "fill_latency_ms": latency_ms,
            "notes": f"{event_type}",
        }

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)


# ── Global singleton instance ──────────────────────────────────────────

_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get or create the global MetricsCollector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def record_score(
    score: ConfluenceScore,
    gate_decision: str = "",
) -> None:
    """Record a confluence score. Convenience wrapper."""
    get_collector().record_score(score, gate_decision)


def record_fill(
    symbol: str,
    position_id: int,
    latency_ms: float,
    fill_price: float,
    lot_size: float,
) -> None:
    """Record a fill event. Convenience wrapper."""
    get_collector().record_fill(symbol, position_id, latency_ms, fill_price, lot_size)


def record_latency(
    symbol: str,
    latency_ms: float,
    event_type: str = "tick_to_signal",
) -> None:
    """Record a latency measurement. Convenience wrapper."""
    get_collector().record_latency(symbol, latency_ms, event_type)

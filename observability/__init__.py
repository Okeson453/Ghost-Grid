"""
observability package public API.
Monitoring, metrics collection, trade journaling, and drift detection.

This is a LEAF NODE module — it imports only from config/ and db/.
Nothing imports from observability/ except callers wanting to log metrics.
"""

from .metrics import MetricsCollector, record_score, record_fill, record_latency
from .trade_journal import TradeJournal, record_trade_opened, record_trade_closed
from .drift_detector import DriftDetector, check_drift
from .daily_report import DailyReporter, generate_daily_report

__all__ = [
    "MetricsCollector",
    "record_score",
    "record_fill",
    "record_latency",
    "TradeJournal",
    "record_trade_opened",
    "record_trade_closed",
    "DriftDetector",
    "check_drift",
    "DailyReporter",
    "generate_daily_report",
]

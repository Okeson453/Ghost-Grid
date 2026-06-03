"""nuclear/models.py — Nuclear event data models."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class NuclearReason(str, Enum):
    """Seven nuclear trigger reasons."""

    COMBINED_PROFIT = "COMBINED_PROFIT"
    DAILY_GAIN_TARGET = "DAILY_GAIN_TARGET"
    LOSS_PROTECTION = "LOSS_PROTECTION"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MARKET_EXHAUSTION = "MARKET_EXHAUSTION"
    LATENCY_ANOMALY = "LATENCY_ANOMALY"
    CORRELATION_SPIKE = "CORRELATION_SPIKE"
    MANUAL_TELEGRAM = "MANUAL_TELEGRAM"


@dataclass(frozen=True)
class NuclearEvent:
    """Immutable record of a nuclear exit event."""

    reason: NuclearReason
    timestamp_ms: int
    positions_closed: int
    portfolio_pnl: float
    equity_at_fire: float

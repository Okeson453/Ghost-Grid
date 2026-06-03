"""
positions/models.py
Position lifecycle enumerations and data models.
"""

from __future__ import annotations
from enum import Enum


class PositionState(str, Enum):
    """Position lifecycle state."""
    IDLE = "IDLE"
    OPENING = "OPENING"
    OPEN_UNREALIZED = "OPEN_UNREALIZED"
    OPEN_LAYER1 = "OPEN_LAYER1"
    OPEN_TRAILING = "OPEN_TRAILING"
    CLOSED_PROFIT = "CLOSED_PROFIT"
    CLOSED_LOSS = "CLOSED_LOSS"
    CLOSED_NUCLEAR = "CLOSED_NUCLEAR"


class ExitReason(str, Enum):
    """Reason for position closure."""
    TRAIL_HIT = "TRAIL_HIT"
    HARD_STOP = "HARD_STOP"
    WEAKNESS_CONFIRMED = "WEAKNESS_CONFIRMED"
    CVD_DIVERGENCE = "CVD_DIVERGENCE"
    NUCLEAR = "NUCLEAR"
    MANUAL_TELEGRAM = "MANUAL_TELEGRAM"
    OFFLINE_STOP = "OFFLINE_STOP"

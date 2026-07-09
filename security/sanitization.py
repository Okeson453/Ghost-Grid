"""
security/sanitization.py
Input validation and sanitization for pipe protocol and system commands.

WHY: Prevent injection attacks via malformed pipe messages or user input.
Uses length limits, character whitelisting, and range validation.
"""

from __future__ import annotations
import re
from typing import Optional


# Maximum field lengths for pipe protocol messages
MAX_SYMBOL_LEN = 10  # "EURUSD" is 6, add buffer for future instruments
MAX_POSITION_ID_LEN = 32  # UUID4-like identifiers
MAX_DESCRIPTION_LEN = 256  # Error descriptions from MT5
MAX_COMMAND_LEN = 500  # Full pipe command

# Character whitelists
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")  # EURUSD, BTCUSD, etc.
POSITION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{1,32}$")  # UUID-like
DIRECTION_VALUES = frozenset(["BUY", "SELL", "NEUTRAL"])
DOMINANT_SIDE_VALUES = frozenset(["BUY", "SELL", "NEUTRAL"])
MESSAGE_TYPE_VALUES = frozenset(["TICK", "FILL", "REJECT", "CLOSED", "HEARTBEAT"])

# Numeric ranges
BID_ASK_MIN = 0.00001  # Minimum realistic price
BID_ASK_MAX = 100000.0  # Maximum realistic price
VOLUME_MIN = 0
VOLUME_MAX = 1_000_000  # Max tick volume
LOTS_MIN = 0.01
LOTS_MAX = 100.0  # Per-trade max
PRICE_RANGE = (BID_ASK_MIN, BID_ASK_MAX)


def sanitize_symbol(value: str) -> Optional[str]:
    """
    Validate symbol string (e.g., 'EURUSD').
    Returns sanitized symbol or None if invalid.
    """
    if not value or len(value) > MAX_SYMBOL_LEN:
        return None
    if not SYMBOL_PATTERN.match(value):
        return None
    return value.upper()


def sanitize_position_id(value: str) -> Optional[str]:
    """
    Validate position ID (UUID or similar).
    Returns sanitized ID or None if invalid.
    """
    if not value or len(value) > MAX_POSITION_ID_LEN:
        return None
    if not POSITION_ID_PATTERN.match(value):
        return None
    return value


def sanitize_direction(value: str) -> Optional[str]:
    """
    Validate direction string ('BUY' or 'SELL').
    Returns direction or None if invalid.
    """
    if value not in DIRECTION_VALUES:
        return None
    return value


def sanitize_dominant_side(value: str) -> Optional[str]:
    """
    Validate dominant side from MT5.
    Returns value or None if invalid.
    """
    if value not in DOMINANT_SIDE_VALUES:
        return None
    return value


def sanitize_message_type(value: str) -> Optional[str]:
    """
    Validate message type enum.
    Returns type or None if invalid.
    """
    if value not in MESSAGE_TYPE_VALUES:
        return None
    return value


def sanitize_description(value: str) -> Optional[str]:
    """
    Validate error description string.
    Truncates to MAX_DESCRIPTION_LEN and removes control characters.
    """
    if not value or len(value) > MAX_DESCRIPTION_LEN:
        return None
    # Remove control characters (< 0x20 and DEL)
    sanitized = "".join(c for c in value if ord(c) >= 0x20)
    return sanitized if sanitized else None


def sanitize_numeric_range(
    value: float,
    min_val: float,
    max_val: float,
) -> Optional[float]:
    """
    Validate numeric value is within range.
    Returns value or None if out of range.
    """
    if not (min_val <= value <= max_val):
        return None
    return value


def sanitize_price(value: float) -> Optional[float]:
    """Validate bid/ask price."""
    return sanitize_numeric_range(value, BID_ASK_MIN, BID_ASK_MAX)


def sanitize_volume(value: int) -> Optional[int]:
    """Validate tick volume."""
    if not isinstance(value, int) or value < VOLUME_MIN or value > VOLUME_MAX:
        return None
    return value


def sanitize_lots(value: float) -> Optional[float]:
    """Validate lot size."""
    return sanitize_numeric_range(value, LOTS_MIN, LOTS_MAX)


def sanitize_timestamp_ms(value: int) -> Optional[int]:
    """
    Validate timestamp (milliseconds since epoch).
    Sanity check: must be between 2020-01-01 and 2050-12-31.
    """
    # 2020-01-01 00:00:00 UTC = 1577836800 seconds = 1577836800000 ms
    # 2050-12-31 23:59:59 UTC = 2524608000 seconds = 2524608000000 ms
    MIN_TS_MS = 1577836800000
    MAX_TS_MS = 2524608000000
    if not isinstance(value, int) or value < MIN_TS_MS or value > MAX_TS_MS:
        return None
    return value


def sanitize_error_code(value: int) -> Optional[int]:
    """
    Validate MT5 error code (1..10000).
    Returns code or None if invalid.
    """
    if not isinstance(value, int) or value < 1 or value > 10000:
        return None
    return value


class SanitizationMetrics:
    """Metrics for input validation."""

    def __init__(self) -> None:
        self.total_validations: int = 0
        self.validation_failures: int = 0
        self.symbols_rejected: int = 0
        self.prices_rejected: int = 0
        self.descriptions_truncated: int = 0

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_validations = 0
        self.validation_failures = 0
        self.symbols_rejected = 0
        self.prices_rejected = 0
        self.descriptions_truncated = 0


_metrics = SanitizationMetrics()


def get_sanitization_metrics() -> SanitizationMetrics:
    """Expose metrics for monitoring."""
    return _metrics

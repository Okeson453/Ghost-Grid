"""
bridge/protocol.py
IPC protocol definition for MT5 ↔ Python communication.

SOURCE: GHOST-GRID-MT5-Design.md § 1.1 IPC Bridge — Named Pipes Protocol

Protocol uses text-based serialization over Windows Named Pipes (\\.\pipe\ghostgrid).
Format: [VERSION_BYTE]|[TYPE]|[FIELD1]|[FIELD2]|...\n

Inbound messages (from MT5 EA every 200ms):
  TICK|symbol|timestamp_ms|bid|ask|tick_volume|dominant_side|cvd_running
  FILL|position_id|symbol|direction|fill_price|lots|mt5_ticket
  REJECT|position_id|error_code|description
  CLOSED|position_id|close_price|lots
  HEARTBEAT|timestamp_ms

Outbound commands (from Python to MT5 EA):
  ORDER|position_id|symbol|direction|lot_size|entry_price|stop_loss
  CLOSE|position_id
  MODSTOP|position_id|new_stop
  NUCLEAR_ALL (close all positions immediately — sent by NuclearController)

Emergency nuclear pathway (bypasses versioning):
  The watchdog thread sends plain NUCLEAR_ALL\n directly to the pipe to ensure
  the message reaches the EA even if the main event loop is stalled. This bypasses
  the standard protocol versioning layer for maximum reliability.

All messages are UTF-8 encoded, V1 protocol version.
WHY text-based: Easy debugging, no binary serialization library needed.
WHY V1 prefix: Allows protocol version negotiation without breaking existing EA.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from config import get_instrument
from security.sanitization import (
    sanitize_symbol,
    sanitize_position_id,
    sanitize_direction,
    sanitize_price,
    sanitize_volume,
    sanitize_lots,
    sanitize_timestamp_ms,
    sanitize_error_code,
    sanitize_dominant_side,
    sanitize_description,
)

logger = logging.getLogger(__name__)

# Protocol constants
PROTOCOL_VERSION = "V1"
FIELD_SEP = "|"
LINE_TERM = "\n"


class InboundType(str, Enum):
    """Message types received from MT5 EA."""

    TICK = "TICK"
    FILL = "FILL"
    REJECT = "REJECT"
    CLOSED = "CLOSED"
    HEARTBEAT = "HEARTBEAT"


class OutboundType(str, Enum):
    """Command types sent to MT5 EA."""

    ORDER = "ORDER"
    CLOSE = "CLOSE"
    MODSTOP = "MODSTOP"
    NUCLEAR_ALL = "NUCLEAR_ALL"


@dataclass(frozen=True)
class TickMessage:
    """Tick message from MT5."""

    symbol: str
    timestamp_ms: int
    bid: float
    ask: float
    tick_volume: int
    dominant_side: str  # "BUY" or "SELL"
    cvd_running: float

    @property
    def mid(self) -> float:
        """Mid-price: (bid + ask) / 2."""
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        """Spread in pips (using instrument pip_size)."""
        inst = get_instrument(self.symbol)
        return (self.ask - self.bid) / inst.pip_size


@dataclass(frozen=True)
class FillMessage:
    """Fill notification from MT5."""

    position_id: str
    symbol: str
    direction: str  # "BUY" or "SELL"
    fill_price: float
    lots: float
    mt5_ticket: int


@dataclass(frozen=True)
class RejectMessage:
    """Order rejection from MT5."""

    position_id: str
    error_code: int
    description: str


@dataclass(frozen=True)
class ClosedMessage:
    """Position closed notification from MT5."""

    position_id: str
    close_price: float
    lots: float


@dataclass(frozen=True)
class HeartbeatMessage:
    """Heartbeat message from MT5 (keep-alive)."""

    timestamp_ms: int


# Type alias for parse result
ParseResult = Union[
    TickMessage,
    FillMessage,
    RejectMessage,
    ClosedMessage,
    HeartbeatMessage,
]


def build_order_command(
    position_id: str,
    symbol: str,
    direction: str,
    lot_size: float,
    entry_price: float,
    stop_loss: float,
) -> str:
    """Build ORDER command string for MT5."""
    return f"{PROTOCOL_VERSION}{FIELD_SEP}{OutboundType.ORDER}{FIELD_SEP}{position_id}{FIELD_SEP}{symbol}{FIELD_SEP}{direction}{FIELD_SEP}{lot_size}{FIELD_SEP}{entry_price}{FIELD_SEP}{stop_loss}{LINE_TERM}"


def build_close_command(position_id: str) -> str:
    """Build CLOSE command string for MT5."""
    return f"{PROTOCOL_VERSION}{FIELD_SEP}{OutboundType.CLOSE}{FIELD_SEP}{position_id}{LINE_TERM}"


def build_modstop_command(position_id: str, new_stop: float) -> str:
    """Build MODSTOP command string for MT5."""
    return f"{PROTOCOL_VERSION}{FIELD_SEP}{OutboundType.MODSTOP}{FIELD_SEP}{position_id}{FIELD_SEP}{new_stop}{LINE_TERM}"


def build_nuclear_command() -> str:
    """
    Build NUCLEAR_ALL command string for MT5 using the standard protocol.
    
    DESIGN NOTE: This builds the versioned format V1|NUCLEAR_ALL\n for use by the main
    trading loop (NuclearController.execute_nuclear). The emergency watchdog bypasses
    this function and writes plain NUCLEAR_ALL\n directly to the pipe to avoid any
    async machinery stalls. Both pathways are valid; the EA accepts both formats.
    """
    return f"{PROTOCOL_VERSION}{FIELD_SEP}{OutboundType.NUCLEAR_ALL}{LINE_TERM}"


class ParseMetrics:
    """Metrics for message parsing and validation."""

    def __init__(self) -> None:
        self.total_parsed: int = 0
        self.parse_errors: int = 0
        self.version_mismatches: int = 0
        self.validation_errors: int = 0
        self.tick_count: int = 0
        self.fill_count: int = 0
        self.reject_count: int = 0
        self.closed_count: int = 0
        self.heartbeat_count: int = 0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_parsed = 0
        self.parse_errors = 0
        self.version_mismatches = 0
        self.validation_errors = 0
        self.tick_count = 0
        self.fill_count = 0
        self.reject_count = 0
        self.closed_count = 0
        self.heartbeat_count = 0


_parse_metrics = ParseMetrics()


def get_parse_metrics() -> ParseMetrics:
    """Get parsing metrics for monitoring and observability."""
    return _parse_metrics


def parse_inbound(raw: str) -> Optional[ParseResult]:
    """
    Parse inbound message with input sanitization. Never raises — returns None on any error.

    Format: [VERSION]|[TYPE]|[FIELDS...]
    Example: V1|TICK|EURUSD|1748823600123|1.08542|1.08545|1250|BUY|3421

    Protocol envelope validation (design: Part I, Section 1.1):
    - Version must be 'V1' (enforced, mismatch increments metric)
    - Type must be one of: TICK, FILL, REJECT, CLOSED, HEARTBEAT
    - Field count validated per message type
    - All string fields sanitized (length limits, character whitelist)
    - All numeric fields validated for type and range

    WHY no exceptions: Pipe communication can receive garbage or partial
    messages during reconnect. Silent parse failure with logging is better
    than crashing the reader loop.

    Increments metrics for observability — enables monitoring of parse health.
    """
    global _parse_metrics

    try:
        # Strip trailing whitespace
        raw = raw.strip()
        if not raw:
            _parse_metrics.parse_errors += 1
            return None

        # Split by field separator
        parts = raw.split(FIELD_SEP)
        if len(parts) < 2:
            _parse_metrics.parse_errors += 1
            return None

        # Validate version
        version = parts[0]
        if version != PROTOCOL_VERSION:
            _parse_metrics.version_mismatches += 1
            return None

        # Route by message type
        msg_type = parts[1]
        _parse_metrics.total_parsed += 1

        if msg_type == InboundType.TICK:
            # TICK|symbol|timestamp_ms|bid|ask|tick_volume|dominant_side|cvd_running
            if len(parts) < 9:
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: symbol with character whitelist
            symbol = sanitize_symbol(parts[2])
            if symbol is None:
                _parse_metrics.validation_errors += 1
                logger.warning(f"Invalid symbol: {parts[2]}")
                return None

            # SANITIZE: timestamp
            try:
                timestamp_ms = sanitize_timestamp_ms(int(parts[3]))
                if timestamp_ms is None:
                    _parse_metrics.validation_errors += 1
                    logger.warning(f"Invalid timestamp: {parts[3]}")
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: bid/ask prices with range check
            try:
                bid = float(parts[4])
                ask = float(parts[5])
                bid = sanitize_price(bid)
                ask = sanitize_price(ask)
                if bid is None or ask is None or ask < bid:
                    _parse_metrics.validation_errors += 1
                    logger.warning(f"Invalid bid/ask: {bid}/{ask}")
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: tick volume with range check
            try:
                tick_volume = sanitize_volume(int(parts[6]))
                if tick_volume is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: dominant_side with enum whitelist
            dominant_side = sanitize_dominant_side(parts[7])
            if dominant_side is None:
                _parse_metrics.validation_errors += 1
                logger.warning(f"Invalid dominant_side: {parts[7]}")
                return None

            # SANITIZE: CVD running (float, no range limit but must be valid)
            try:
                cvd_running = float(parts[8])
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            _parse_metrics.tick_count += 1
            return TickMessage(
                symbol=symbol,
                timestamp_ms=timestamp_ms,
                bid=bid,
                ask=ask,
                tick_volume=tick_volume,
                dominant_side=dominant_side,
                cvd_running=cvd_running,
            )

        elif msg_type == InboundType.FILL:
            # FILL|position_id|symbol|direction|fill_price|lots|mt5_ticket
            if len(parts) < 9:
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: position_id with character whitelist
            position_id = sanitize_position_id(parts[2])
            if position_id is None:
                _parse_metrics.validation_errors += 1
                logger.warning(f"Invalid position_id: {parts[2]}")
                return None

            # SANITIZE: symbol
            symbol = sanitize_symbol(parts[3])
            if symbol is None:
                _parse_metrics.validation_errors += 1
                logger.warning(f"Invalid symbol: {parts[3]}")
                return None

            # SANITIZE: direction enum
            direction = sanitize_direction(parts[4])
            if direction is None:
                _parse_metrics.validation_errors += 1
                logger.warning(f"Invalid direction: {parts[4]}")
                return None

            # SANITIZE: fill_price
            try:
                fill_price = float(parts[5])
                fill_price = sanitize_price(fill_price)
                if fill_price is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: lots
            try:
                lots = float(parts[6])
                lots = sanitize_lots(lots)
                if lots is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # mt5_ticket: integer, no sanitization needed beyond type check
            try:
                mt5_ticket = int(parts[7])
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            _parse_metrics.fill_count += 1
            return FillMessage(
                position_id=position_id,
                symbol=symbol,
                direction=direction,
                fill_price=fill_price,
                lots=lots,
                mt5_ticket=mt5_ticket,
            )

        elif msg_type == InboundType.REJECT:
            # REJECT|position_id|error_code|description (description may have pipes)
            if len(parts) < 4:
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: position_id
            position_id = sanitize_position_id(parts[2])
            if position_id is None:
                _parse_metrics.validation_errors += 1
                return None

            # SANITIZE: error_code
            try:
                error_code = sanitize_error_code(int(parts[3]))
                if error_code is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: description (rejoin in case it contains pipes, remove control chars)
            description = FIELD_SEP.join(parts[4:])
            description = sanitize_description(description)
            if description is None:
                _parse_metrics.validation_errors += 1
                return None

            _parse_metrics.reject_count += 1
            return RejectMessage(
                position_id=position_id,
                error_code=error_code,
                description=description,
            )

        elif msg_type == InboundType.CLOSED:
            # CLOSED|position_id|close_price|lots
            if len(parts) < 5:
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: position_id
            position_id = sanitize_position_id(parts[2])
            if position_id is None:
                _parse_metrics.validation_errors += 1
                return None

            # SANITIZE: close_price
            try:
                close_price = float(parts[3])
                close_price = sanitize_price(close_price)
                if close_price is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            # SANITIZE: lots
            try:
                lots = float(parts[4])
                lots = sanitize_lots(lots)
                if lots is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            _parse_metrics.closed_count += 1
            return ClosedMessage(
                position_id=position_id,
                close_price=close_price,
                lots=lots,
            )

        elif msg_type == InboundType.HEARTBEAT:
            # HEARTBEAT|timestamp_ms
            if len(parts) < 3:
                _parse_metrics.parse_errors += 1
                return None

            try:
                timestamp_ms = sanitize_timestamp_ms(int(parts[2]))
                if timestamp_ms is None:
                    _parse_metrics.validation_errors += 1
                    return None
            except (ValueError, TypeError):
                _parse_metrics.parse_errors += 1
                return None

            _parse_metrics.heartbeat_count += 1
            return HeartbeatMessage(timestamp_ms=timestamp_ms)

        else:
            # Unknown message type
            return None

    except Exception as e:
        logger.error(f"Parse error (generic): {e}")
        _parse_metrics.parse_errors += 1
        return None

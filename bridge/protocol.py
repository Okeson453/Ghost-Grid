"""
bridge/protocol.py
IPC protocol definition for MT5 ↔ Python communication.

Protocol uses text-based serialization over Windows Named Pipes.
Format: [VERSION_BYTE]|[TYPE]|[FIELD1]|[FIELD2]|...\n

All messages are UTF-8 encoded. Inbound messages come from MT5 EA.
Outbound messages are sent as commands to MT5 EA.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from config import get_instrument


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
    """Build NUCLEAR_ALL command string for MT5."""
    return f"{PROTOCOL_VERSION}{FIELD_SEP}{OutboundType.NUCLEAR_ALL}{LINE_TERM}"


def parse_inbound(raw: str) -> Optional[ParseResult]:
    """
    Parse inbound message. Never raises — returns None on any error.
    
    Format: [VERSION]|[TYPE]|[FIELDS...]
    
    WHY no exceptions: Pipe communication can receive garbage or partial
    messages during reconnect. Silent parse failure with logging is better
    than crashing the reader loop.
    """
    try:
        # Strip trailing whitespace
        raw = raw.strip()
        if not raw:
            return None

        # Split by field separator
        parts = raw.split(FIELD_SEP)
        if len(parts) < 2:
            return None

        # Validate version
        version = parts[0]
        if version != PROTOCOL_VERSION:
            return None

        # Route by message type
        msg_type = parts[1]

        if msg_type == InboundType.TICK:
            # TICK|symbol|timestamp_ms|bid|ask|tick_volume|dominant_side|cvd_running
            if len(parts) < 9:
                return None
            return TickMessage(
                symbol=parts[2],
                timestamp_ms=int(parts[3]),
                bid=float(parts[4]),
                ask=float(parts[5]),
                tick_volume=int(parts[6]),
                dominant_side=parts[7],
                cvd_running=float(parts[8]),
            )

        elif msg_type == InboundType.FILL:
            # FILL|position_id|symbol|direction|fill_price|lots|mt5_ticket
            if len(parts) < 8:
                return None
            return FillMessage(
                position_id=parts[2],
                symbol=parts[3],
                direction=parts[4],
                fill_price=float(parts[5]),
                lots=float(parts[6]),
                mt5_ticket=int(parts[7]),
            )

        elif msg_type == InboundType.REJECT:
            # REJECT|position_id|error_code|description (description may have pipes)
            if len(parts) < 4:
                return None
            # Rejoin description in case it contains pipes
            description = FIELD_SEP.join(parts[4:])
            return RejectMessage(
                position_id=parts[2],
                error_code=int(parts[3]),
                description=description,
            )

        elif msg_type == InboundType.CLOSED:
            # CLOSED|position_id|close_price|lots
            if len(parts) < 5:
                return None
            return ClosedMessage(
                position_id=parts[2],
                close_price=float(parts[3]),
                lots=float(parts[4]),
            )

        elif msg_type == InboundType.HEARTBEAT:
            # HEARTBEAT|timestamp_ms
            if len(parts) < 3:
                return None
            return HeartbeatMessage(timestamp_ms=int(parts[2]))

        else:
            # Unknown message type
            return None

    except (ValueError, IndexError, TypeError):
        # Malformed message
        return None

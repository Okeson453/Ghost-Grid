"""
execution/fill_handler.py
Parse FILL/REJECT/FAILED responses from MT5 via named pipe.
WHY: Isolated parsing enables unit testing and robust error handling.
"""

from __future__ import annotations
import asyncio
from typing import Optional

from bridge.protocol import FillMessage, RejectMessage, ClosedMessage, parse_inbound
from .models import FillResult, OrderStatus, FillHandlerMetrics


class FillHandler:
    """
    Parse responses from MT5 pipe reader.
    WHY: Decouples parsing logic from I/O, enables metrics.
    """

    def __init__(self, reader_or_queue: Optional[object] = None):
        self._metrics = FillHandlerMetrics()
        # Accept either a PipeReader instance or an asyncio.Queue for fills
        self._fill_queue: Optional[asyncio.Queue] = None
        if reader_or_queue is not None:
            # If a PipeReader was provided, extract its internal fill queue
            if hasattr(reader_or_queue, "_fill_queue"):
                self._fill_queue = getattr(reader_or_queue, "_fill_queue")
            # If a raw queue was provided, use it directly
            elif isinstance(reader_or_queue, asyncio.Queue):
                self._fill_queue = reader_or_queue

    def parse_response(self, response: str) -> Optional[FillResult]:
        """
        Parse a response line from MT5.

        The execution layer now requires the versioned protocol payloads from
        bridge/protocol.py before a fill is considered real. Legacy strings are
        still parsed for backwards compatibility with existing tests.
        """
        try:
            raw = response.strip()
            if not raw:
                self._metrics.malformed_responses += 1
                return None

            if raw.startswith("V1|"):
                parsed = parse_inbound(raw)
                if isinstance(parsed, FillMessage):
                    return self._parse_fill_message(parsed)
                if isinstance(parsed, RejectMessage):
                    return self._parse_reject_message(parsed)
                if isinstance(parsed, ClosedMessage):
                    return self._parse_closed_message(parsed)
                self._metrics.malformed_responses += 1
                return None

            parts = raw.split("|")
            if not parts:
                self._metrics.malformed_responses += 1
                return None

            response_type = parts[0]
            if response_type == "FILL":
                return self._parse_fill(parts)
            if response_type == "REJECT":
                return self._parse_reject(parts)
            if response_type == "FAILED":
                return self._parse_failed(parts)
            self._metrics.malformed_responses += 1
            return None

        except Exception:
            self._metrics.parse_errors += 1
            return None

    def _parse_fill_message(self, msg: FillMessage) -> Optional[FillResult]:
        """Convert a protocol FillMessage into a FillResult."""
        try:
            return FillResult(
                status=OrderStatus.FILL,
                symbol=msg.symbol,
                position_id=int(msg.position_id),
                fill_price=float(msg.fill_price),
                fill_time_ms=int(asyncio.get_event_loop().time() * 1000),
                request_id=str(msg.mt5_ticket),
                reason=None,
            )
        except Exception:
            self._metrics.parse_errors += 1
            return None
        finally:
            self._metrics.fills_received += 1

    def _parse_reject_message(self, msg: RejectMessage) -> Optional[FillResult]:
        """Convert a protocol RejectMessage into a FillResult."""
        try:
            return FillResult(
                status=OrderStatus.REJECT,
                symbol="",
                position_id=int(msg.position_id),
                fill_price=0.0,
                fill_time_ms=0,
                request_id=str(msg.position_id),
                reason=msg.description,
            )
        except Exception:
            self._metrics.parse_errors += 1
            return None
        finally:
            self._metrics.rejects_received += 1

    def _parse_closed_message(self, msg: ClosedMessage) -> Optional[FillResult]:
        """Convert a protocol ClosedMessage into an inert fill result."""
        try:
            return FillResult(
                status=OrderStatus.FAILED,
                symbol=msg.position_id,
                position_id=int(msg.position_id),
                fill_price=float(msg.close_price),
                fill_time_ms=0,
                request_id=str(msg.position_id),
                reason="CLOSED",
            )
        except Exception:
            self._metrics.parse_errors += 1
            return None

    def _parse_fill(self, parts: list[str]) -> Optional[FillResult]:
        """Parse legacy FILL|symbol|position_id|fill_price|fill_time_ms|request_id."""
        try:
            if len(parts) < 6:
                self._metrics.malformed_responses += 1
                return None

            return FillResult(
                status=OrderStatus.FILL,
                symbol=parts[1],
                position_id=int(parts[2]),
                fill_price=float(parts[3]),
                fill_time_ms=int(parts[4]),
                request_id=parts[5],
                reason=None,
            )
        except (ValueError, IndexError) as e:
            self._metrics.parse_errors += 1
            return None
        finally:
            self._metrics.fills_received += 1

    def _parse_reject(self, parts: list[str]) -> Optional[FillResult]:
        """Parse REJECT|reason"""
        try:
            if len(parts) < 2:
                self._metrics.malformed_responses += 1
                return None

            # REJECT is order-level (no position_id)
            return FillResult(
                status=OrderStatus.REJECT,
                symbol="",
                position_id=0,
                fill_price=0.0,
                fill_time_ms=0,
                request_id="",
                reason=parts[1],
            )
        except Exception as e:
            self._metrics.parse_errors += 1
            return None
        finally:
            self._metrics.rejects_received += 1

    def _parse_failed(self, parts: list[str]) -> Optional[FillResult]:
        """Parse FAILED|position_id|reason"""
        try:
            if len(parts) < 3:
                self._metrics.malformed_responses += 1
                return None

            return FillResult(
                status=OrderStatus.FAILED,
                symbol="",
                position_id=int(parts[1]),
                fill_price=0.0,
                fill_time_ms=0,
                request_id="",
                reason=parts[2],
            )
        except (ValueError, IndexError) as e:
            self._metrics.parse_errors += 1
            return None
        finally:
            self._metrics.failed_received += 1

    async def wait_for_fill(self, request_id: str, timeout_s: float = 3.0) -> Optional[FillResult]:
        """
        Wait for a Fill/Reject/Failed message matching `request_id` on the
        configured fill queue. Returns FillResult or None on timeout.
        """
        if self._fill_queue is None:
            return None

        try:
            end_ts = asyncio.get_event_loop().time() + timeout_s
            while True:
                remaining = end_ts - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None
                msg = await asyncio.wait_for(self._fill_queue.get(), timeout=remaining)

                # msg is a protocol dataclass (FillMessage/RejectMessage/ClosedMessage)
                # Match by position_id if available, or mt5_ticket when provided.
                try:
                    if isinstance(msg, FillMessage):
                        return self._parse_fill_message(msg)
                    if isinstance(msg, RejectMessage):
                        return self._parse_reject_message(msg)
                    if hasattr(msg, "position_id") and str(msg.position_id) == str(request_id):
                        if hasattr(msg, "fill_price"):
                            return FillResult(
                                status=OrderStatus.FILL,
                                symbol=getattr(msg, "symbol", ""),
                                position_id=int(msg.position_id),
                                fill_price=float(getattr(msg, "fill_price", 0.0)),
                                fill_time_ms=int(asyncio.get_event_loop().time() * 1000),
                                request_id=str(request_id),
                            )
                        return FillResult(
                            status=OrderStatus.REJECT,
                            symbol="",
                            position_id=int(getattr(msg, "position_id", 0)),
                            fill_price=0.0,
                            fill_time_ms=int(asyncio.get_event_loop().time() * 1000),
                            request_id=str(request_id),
                            reason=getattr(msg, "description", None),
                        )
                except Exception:
                    # Ignore malformed messages and continue waiting until timeout
                    continue

        except asyncio.TimeoutError:
            return None

    @property
    def metrics(self) -> FillHandlerMetrics:
        """Expose metrics."""
        return self._metrics

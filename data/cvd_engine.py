"""
data/cvd_engine.py
CVD (Cumulative Volume Delta) ring buffer with session boundary markers.

The CVD ring buffer stores historical CVD values in a fixed-size deque.
Session boundaries are marked by inserting 0.0 when the session changes.
This allows downstream regime detection to know when a new trading session
started, and to reset statistics across session boundaries.
"""

from __future__ import annotations
from collections import deque

from config import CVD_RING_BUFFER_SIZE


class CVDMetrics:
    """Metrics for CVD engine."""
    def __init__(self) -> None:
        self.total_updates: int = 0
        self.session_boundaries: int = 0
        self.buffer_overflows: int = 0  # Ring buffer capacity exceeded

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_updates = 0
        self.session_boundaries = 0
        self.buffer_overflows = 0


class CVDEngine:
    """CVD ring buffer with session boundary detection."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._buffer: deque[float] = deque(maxlen=CVD_RING_BUFFER_SIZE)
        self._last_session: str | None = None
        self._metrics = CVDMetrics()

    @property
    def metrics(self) -> CVDMetrics:
        """Get CVD metrics."""
        return self._metrics

    def on_bar_close(self, cvd_value: float, session: str) -> None:
        """
        Append CVD value to ring buffer.
        If session changed, insert a 0.0 boundary marker first.

        WHY session boundary marker: Downstream regime detection needs to know
        session boundaries to reset statistics (e.g., session_start_bid, session_start_ask)
        and prevent mixing CVD from different sessions. The 0.0 marker signals
        a break in continuity without requiring a separate timestamp list.
        """
        self._metrics.total_updates += 1
        
        if session != self._last_session and self._last_session is not None:
            # Session boundary — insert marker
            if len(self._buffer) >= CVD_RING_BUFFER_SIZE - 1:
                self._metrics.buffer_overflows += 1
            self._buffer.append(0.0)
            self._metrics.session_boundaries += 1
        self._last_session = session
        self._buffer.append(cvd_value)

    def history(self) -> list[float]:
        """Return buffer contents as list, oldest-first."""
        return list(self._buffer)

    def __len__(self) -> int:
        """Return number of CVD values in buffer."""
        return len(self._buffer)

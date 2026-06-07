"""
data/cvd_engine.py
CVD (Cumulative Volume Delta) ring buffer with session boundary markers.

The CVD ring buffer stores historical CVD values in a fixed-size deque.
Session boundaries are marked by inserting 0.0 when the session changes.
This allows downstream regime detection to know when a new trading session
started, and to reset statistics across session boundaries.

Implements Kalman filter approximation via exponential smoothing (α=0.15)
for divergence detection: Z-score on (raw_cvd - smoothed_cvd).
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass

from config import CVD_RING_BUFFER_SIZE


@dataclass
class CVDSignal:
    """Result of CVD divergence detection."""
    divergence_confirmed: bool  # |Z-score| > 2.0 with direction mismatch
    z_score: float              # Residual Z-score
    direction: str              # "BUY" | "SELL" | "NEUTRAL"
    trend_aligned: bool         # CVD & price trend agree


class CVDMetrics:
    """Metrics for CVD engine."""
    def __init__(self) -> None:
        self.total_updates: int = 0
        self.session_boundaries: int = 0
        self.buffer_overflows: int = 0  # Ring buffer capacity exceeded
        self.divergences_detected: int = 0

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_updates = 0
        self.session_boundaries = 0
        self.buffer_overflows = 0
        self.divergences_detected = 0


class CVDEngine:
    """CVD ring buffer with session boundary detection and divergence analysis."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._buffer: deque[float] = deque(maxlen=CVD_RING_BUFFER_SIZE)
        self._smoothed: deque[float] = deque(maxlen=CVD_RING_BUFFER_SIZE)
        self._last_session: str | None = None
        self._metrics = CVDMetrics()
        self._kalman_alpha = 0.15  # Exponential smoothing factor

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
            self._smoothed.append(0.0)
            self._metrics.session_boundaries += 1
        self._last_session = session
        self._buffer.append(cvd_value)
        
        # Update exponential moving average (Kalman approximation)
        if len(self._smoothed) == 0:
            self._smoothed.append(cvd_value)
        else:
            ema = self._kalman_alpha * cvd_value + (1.0 - self._kalman_alpha) * self._smoothed[-1]
            self._smoothed.append(ema)

    def history(self) -> list[float]:
        """Return buffer contents as list, oldest-first."""
        return list(self._buffer)

    def detect_divergence(self, price_trend: float) -> CVDSignal:
        """
        Detect CVD divergence: price_trend vs cvd_trend mismatch.
        
        Inputs:
          price_trend: close[now] - close[10 bars ago] (direction & magnitude)
        
        Returns:
          divergence_confirmed: true if |Z| > 2.0 AND direction mismatch
          z_score: residual deviation (raw - smoothed) / std(residuals)
          direction: "SELL" if bullish price / bearish CVD, else "BUY"
          trend_aligned: true if price & CVD trend agree
        
        Logic:
          - Bullish divergence: price up, CVD down → SHORT signal
          - Bearish divergence: price down, CVD up → LONG signal
        """
        if len(self._buffer) < 20 or len(self._smoothed) < 20:
            return CVDSignal(
                divergence_confirmed=False,
                z_score=0.0,
                direction="NEUTRAL",
                trend_aligned=False
            )
        
        # Calculate residuals (raw - smoothed)
        raw_list = list(self._buffer)
        smoothed_list = list(self._smoothed)
        residuals = [r - s for r, s in zip(raw_list[-20:], smoothed_list[-20:])]
        
        # Compute standard deviation
        mean_residual = sum(residuals) / len(residuals)
        variance = sum((r - mean_residual) ** 2 for r in residuals) / len(residuals)
        std_residual = variance ** 0.5 if variance > 0 else 1e-9
        
        # Z-score of current residual
        current_residual = raw_list[-1] - smoothed_list[-1]
        z_score = current_residual / std_residual if std_residual > 0 else 0.0
        
        # CVD trend: last value vs 10 bars ago
        cvd_trend = raw_list[-1] - raw_list[-10] if len(raw_list) >= 10 else 0.0
        
        # Determine divergence & direction
        price_up = price_trend > 0
        cvd_up = cvd_trend > 0
        
        divergence = (price_up and not cvd_up) or (not price_up and cvd_up)
        divergence_confirmed = divergence and abs(z_score) > 2.0
        
        if divergence_confirmed:
            self._metrics.divergences_detected += 1
        
        # Direction: bullish price / bearish CVD = SHORT signal
        direction = "SELL" if (price_up and not cvd_up) else "BUY" if (not price_up and cvd_up) else "NEUTRAL"
        trend_aligned = not divergence
        
        return CVDSignal(
            divergence_confirmed=divergence_confirmed,
            z_score=z_score,
            direction=direction,
            trend_aligned=trend_aligned
        )

    def __len__(self) -> int:
        """Return number of CVD values in buffer."""
        return len(self._buffer)

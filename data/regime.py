"""
data/regime.py
Simplified 4-state regime fingerprint classifier.

Replaces the 8-state regime from PHANTOM GRID with 4 states detectable
purely from MT5 data:
  - TREND: Strong directional move, ATR expanding, EMA fanned
  - CHOP: ATR contracting, price oscillating, no EMA separation
  - BREAKOUT: Recent structure break, volume spike, spread widening
  - REVERSAL: Momentum exhaustion, BOS + CHoCH confirmed

No external feeds required (no DXY, VIX, BTC.D).
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import MarketSnapshot


class Regime(Enum):
    """4-state regime classification."""
    TREND    = "TREND"
    CHOP     = "CHOP"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"


@dataclass
class RegimeSignal:
    """Regime detection output."""
    regime: Regime
    confidence: float        # 0.0–1.0 (higher = stronger signal)
    primary_reason: str      # e.g., "EMA_SEPARATION_HIGH"
    atr_ratio: float         # ATR_1m / ATR_5m
    ema_separation: float    # 0–1 normalized


class RegimeClassifier:
    """Classifies market regime from snapshot indicators."""

    def __init__(self) -> None:
        self._last_regime = Regime.CHOP
        self._regime_bars = 0  # Consecutive bars in current regime

    def classify(self, snap: MarketSnapshot) -> RegimeSignal:
        """
        Classify regime from a MarketSnapshot.
        
        Uses 4 primary inputs:
          1. atr_ratio = ATR_1m / ATR_5m  (>1.1 = expanding volatility)
          2. ema_separation = EMA ribbon spread (0–1 normalized)
          3. rsi_7 = RSI(7) on M1 (extremes indicate momentum)
          4. vol_ratio = current tick volume / average (outliers)
        
        Returns RegimeSignal with regime, confidence, and diagnostic info.
        """
        # Guard: ensure we have valid data
        if snap.atr_1m <= 0 or snap.atr_5m <= 0:
            return RegimeSignal(
                regime=Regime.CHOP,
                confidence=0.0,
                primary_reason="INSUFFICIENT_DATA",
                atr_ratio=0.0,
                ema_separation=0.0,
            )

        # Calculate base indicators
        atr_ratio = snap.atr_1m / snap.atr_5m if snap.atr_5m > 0 else 1.0
        ema_sep = self._compute_ema_separation(snap)
        rsi_7 = self._compute_rsi_fast(snap.m1)
        vol_ratio = self._compute_volume_ratio(snap)

        # --- TREND Detection ---
        # Strong directional + expanding ATR + good EMA alignment
        if (ema_sep > 0.6 and atr_ratio > 1.05 and vol_ratio > 0.9 and 
            (rsi_7 > 60 or rsi_7 < 40)):
            confidence = min(0.95, (ema_sep * atr_ratio * vol_ratio) / 2.5)
            return RegimeSignal(
                regime=Regime.TREND,
                confidence=confidence,
                primary_reason="HIGH_EMA_SEP_EXPANDING_ATR",
                atr_ratio=atr_ratio,
                ema_separation=ema_sep,
            )

        # --- CHOP Detection ---
        # Low EMA separation + contracting ATR + neutral momentum
        if ema_sep < 0.25 and atr_ratio < 0.95 and not (rsi_7 > 70 or rsi_7 < 30):
            confidence = min(0.95, 1.0 - ema_sep)
            return RegimeSignal(
                regime=Regime.CHOP,
                confidence=confidence,
                primary_reason="LOW_EMA_SEP_CONTRACTING_ATR",
                atr_ratio=atr_ratio,
                ema_separation=ema_sep,
            )

        # --- BREAKOUT Detection ---
        # Very high volume spike + BOS detected + ATR expansion
        if (vol_ratio > 2.0 and atr_ratio > 1.0 and 
            self._detect_recent_bos(snap)):
            confidence = min(0.95, vol_ratio / 4.0)
            return RegimeSignal(
                regime=Regime.BREAKOUT,
                confidence=confidence,
                primary_reason="HIGH_VOLUME_BOS_DETECTED",
                atr_ratio=atr_ratio,
                ema_separation=ema_sep,
            )

        # --- REVERSAL Detection ---
        # CHoCH + RSI extreme + momentum divergence
        if (self._detect_choch(snap) and (rsi_7 > 75 or rsi_7 < 25) and
            self._detect_momentum_exhaustion(snap)):
            confidence = min(0.95, abs(rsi_7 - 50.0) / 50.0)
            return RegimeSignal(
                regime=Regime.REVERSAL,
                confidence=confidence,
                primary_reason="CHOCH_CONFIRMED_RSI_EXTREME",
                atr_ratio=atr_ratio,
                ema_separation=ema_sep,
            )

        # Default to CHOP if no strong pattern
        return RegimeSignal(
            regime=Regime.CHOP,
            confidence=0.3,
            primary_reason="NO_STRONG_PATTERN",
            atr_ratio=atr_ratio,
            ema_separation=ema_sep,
        )

    def _compute_ema_separation(self, snap: MarketSnapshot) -> float:
        """
        Compute EMA ribbon separation as 0–1 normalized value.
        Adaptive EMA: 8, 13, 21, 34 periods on M1.
        
        Fully separated (fanned): all EMAs in order → 1.0
        Converged (flat): all EMAs within 0.0003 → 0.0
        """
        m1 = snap.m1
        if len(snap.m1) < 34:  # Need at least 34 bars for EMA-34
            return 0.0

        # Simplified: use M1 close and ATR as proxy for EMA positions
        # Full EMA calculation would require separate module; approximation here:
        close = m1.close
        open_ = m1.open
        body = abs(close - open_)
        
        # Approximate EMA separation as ratio of body to ATR
        if snap.atr_1m > 0:
            separation = body / snap.atr_1m
            # Normalize to 0–1 (anything > 2.0 ATR = fully separated)
            return min(1.0, max(0.0, separation / 2.0))
        return 0.0

    def _compute_rsi_fast(self, m1_bar) -> float:
        """
        Simplified RSI(7) approximation using M1 bar.
        
        In production, this would track 7 bars of gains/losses.
        Here, single-bar approximation: RSI = 50 + 50 * normalized_return.
        
        Range: 0–100 (normal), but extremes are >75 (bullish) or <25 (bearish).
        """
        if not hasattr(m1_bar, 'close') or not hasattr(m1_bar, 'open'):
            return 50.0
        
        body_range = m1_bar.high - m1_bar.low
        if body_range <= 0:
            return 50.0
        
        close_pos = (m1_bar.close - m1_bar.low) / body_range
        return 25.0 + (close_pos * 50.0)  # Approximation: RSI = 25 + 50 * close_pos

    def _compute_volume_ratio(self, snap: MarketSnapshot) -> float:
        """
        Volume ratio: current tick volume / average of last 5 M1 bars.
        
        Returns normalized ratio (1.0 = average, >2.0 = spike).
        """
        if snap.tick.tick_volume == 0:
            return 0.5
        
        # Use M1 volume as proxy for average
        if hasattr(snap, 'm1') and snap.m1.volume > 0:
            return snap.tick.tick_volume / snap.m1.volume
        return 1.0

    def _detect_recent_bos(self, snap: MarketSnapshot) -> bool:
        """
        Detect Break of Structure: price closed beyond recent swing high/low.
        
        Simplified: if M1 close > M3 high or M1 close < M3 low, BOS confirmed.
        """
        if not snap.m1 or not snap.m3:
            return False
        
        return snap.m1.close > snap.m3.high or snap.m1.close < snap.m3.low

    def _detect_choch(self, snap: MarketSnapshot) -> bool:
        """
        Detect Change of Character: lower low (or higher high) below/above
        previous swing structure.
        
        Simplified: if M1 low < M5 low (bearish) or M1 high > M5 high (bullish).
        """
        if not snap.m1 or not snap.m5:
            return False
        
        return (snap.m1.low < snap.m5.low * 0.9999 or 
                snap.m1.high > snap.m5.high * 1.0001)

    def _detect_momentum_exhaustion(self, snap: MarketSnapshot) -> bool:
        """
        Detect momentum exhaustion: price making lower highs or higher lows
        while RSI is extreme.
        
        Simplified: if M1 upper wick > lower wick AND M1 is small-bodied.
        """
        if not snap.m1:
            return False
        
        body = abs(snap.m1.close - snap.m1.open)
        upper_wick = snap.m1.high - max(snap.m1.close, snap.m1.open)
        lower_wick = min(snap.m1.close, snap.m1.open) - snap.m1.low
        
        # Exhaustion: large upper wick (rejection) + small body
        return upper_wick > lower_wick and body < snap.atr_1m * 0.3

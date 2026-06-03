"""
execution/leverage.py
Dynamic leverage calculator based on ATR %.
WHY: Inverse relationship between volatility and risk tolerance.
Lower ATR% = lower volatility = higher leverage allowed (up to 30×)
Higher ATR% = higher volatility = lower leverage (1× = manual size)
"""

from __future__ import annotations
from .models import LeverageMetrics


class LeverageCalculator:
    """
    Calculate dynamic leverage multiplier based on ATR %.
    WHY: Dynamically adjust position size for current market conditions.
    """

    # Leverage buckets: ATR% range → multiplier
    # ATR% = (ATR / current_price) * 100
    LEVERAGE_BUCKETS = [
        (0.0, 0.5, 30),      # 0.0–0.5% ATR → 30× leverage (very stable)
        (0.5, 1.0, 20),      # 0.5–1.0% ATR → 20× leverage
        (1.0, 1.5, 10),      # 1.0–1.5% ATR → 10× leverage
        (1.5, 2.5, 5),       # 1.5–2.5% ATR → 5× leverage
        (2.5, 5.0, 2),       # 2.5–5.0% ATR → 2× leverage
        (5.0, 100.0, 1),     # 5.0%+ ATR → 1× leverage (high volatility)
    ]

    def __init__(self):
        self._metrics = LeverageMetrics()

    def calculate_leverage(
        self,
        atr: float,
        current_price: float,
    ) -> int:
        """
        Calculate leverage multiplier.

        Args:
            atr: Current Average True Range value
            current_price: Current bid/mid price

        Returns: Leverage multiplier (1, 2, 5, 10, 20, 30)
        """
        try:
            self._metrics.leverage_calculations += 1

            if current_price <= 0 or atr < 0:
                self._metrics.calculation_errors += 1
                return 1  # Safe default

            # Calculate ATR%
            atr_pct = (atr / current_price) * 100

            # Find matching bucket
            for min_atr, max_atr, multiplier in self.LEVERAGE_BUCKETS:
                if min_atr <= atr_pct < max_atr:
                    self._track_leverage_bucket(multiplier)
                    return multiplier

            # Fallback (shouldn't reach here)
            self._metrics.calculation_errors += 1
            return 1

        except Exception as e:
            self._metrics.calculation_errors += 1
            return 1

    def _track_leverage_bucket(self, multiplier: int) -> None:
        """Increment counter for the selected leverage bucket."""
        if multiplier == 1:
            self._metrics.leverage_1x_count += 1
        elif multiplier == 2:
            # Track 2× as part of 10× for simplicity (not explicitly bucketed)
            pass
        elif multiplier == 5:
            # Track 5× as part of 10×
            pass
        elif multiplier == 10:
            self._metrics.leverage_10x_count += 1
        elif multiplier == 20:
            self._metrics.leverage_20x_count += 1
        elif multiplier == 30:
            self._metrics.leverage_30x_count += 1

    def apply_leverage(
        self,
        base_lot_size: float,
        leverage_multiplier: int,
    ) -> float:
        """
        Apply leverage multiplier to base lot size.
        WHY: Separate calculation from application enables testing.
        """
        return base_lot_size * leverage_multiplier

    @property
    def metrics(self) -> LeverageMetrics:
        """Expose metrics."""
        return self._metrics

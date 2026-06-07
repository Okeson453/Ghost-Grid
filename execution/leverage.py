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
    # From design spec: ATR% < 0.8% → 30x, 0.8–1.5% → 20x, > 1.5% → 10x
    # ATR% = (ATR / current_price) * 100
    LEVERAGE_BUCKETS = [
        (0.0, 0.8, 30),  # 0.0–0.8% ATR → 30× leverage (very stable)
        (0.8, 1.5, 20),  # 0.8–1.5% ATR → 20× leverage (moderate volatility)
        (1.5, 100.0, 10),  # 1.5%+ ATR → 10× leverage (higher volatility)
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
        if multiplier == 10:
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

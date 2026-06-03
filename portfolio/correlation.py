"""
portfolio/correlation.py
Pairwise Pearson correlation for all open positions.

Computes rolling correlation matrix across all open positions
and updates PortfolioState.avg_pair_correlation every 60s.

WHY: Reduces basket risk by flagging when all trades move together.
     Defensively reduces position sizes if avg correlation > 0.8.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Tuple, Optional
from portfolio.state import PortfolioState

logger = logging.getLogger(__name__)


def calculate_correlation(values1: List[float], values2: List[float]) -> Optional[float]:
    """
    Calculate Pearson correlation coefficient between two lists.

    Args:
        values1: First list of values
        values2: Second list of values

    Returns:
        Correlation coefficient (-1.0 to 1.0), or None if calculation fails
    """
    if len(values1) < 2 or len(values2) < 2:
        return None

    if len(values1) != len(values2):
        return None

    mean1 = sum(values1) / len(values1)
    mean2 = sum(values2) / len(values2)

    numerator = sum((values1[i] - mean1) * (values2[i] - mean2) for i in range(len(values1)))
    
    variance1 = sum((v - mean1) ** 2 for v in values1)
    variance2 = sum((v - mean2) ** 2 for v in values2)

    denominator = (variance1 * variance2) ** 0.5

    if denominator == 0:
        return None

    return numerator / denominator


class CorrelationEngine:
    """
    Computes and updates portfolio correlation metrics.
    Called every 60 seconds by the main event loop.
    """

    def __init__(self, window_size: int = 50):
        """
        Initialize correlation engine.

        Args:
            window_size: Number of ticks to use for correlation calculation
        """
        self.window_size = window_size
        # symbol -> list of recent prices (max window_size)
        self.price_windows: Dict[str, List[float]] = {}

    def record_price(self, symbol: str, price: float) -> None:
        """
        Record a price update for a symbol.

        Args:
            symbol: Instrument symbol (e.g., "EURUSD")
            price: Current price
        """
        if symbol not in self.price_windows:
            self.price_windows[symbol] = []

        self.price_windows[symbol].append(price)

        # Keep window size limited
        if len(self.price_windows[symbol]) > self.window_size:
            self.price_windows[symbol].pop(0)

    def compute_portfolio_correlation(self, state: PortfolioState) -> float:
        """
        Compute average pairwise correlation across all open positions.

        Args:
            state: Current portfolio state

        Returns:
            Average correlation coefficient (0.0-1.0)
        """
        if len(state.open_positions) < 2:
            # Can't correlate with less than 2 positions
            return 0.0

        symbols = [p.symbol for p in state.open_positions.values() if hasattr(p, 'symbol')]
        symbols = list(set(symbols))  # Unique symbols

        if len(symbols) < 2:
            return 0.0

        # Compute all pairwise correlations
        correlations = []
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1 = symbols[i]
                sym2 = symbols[j]

                if sym1 not in self.price_windows or sym2 not in self.price_windows:
                    continue

                prices1 = self.price_windows[sym1]
                prices2 = self.price_windows[sym2]

                if len(prices1) < 2 or len(prices2) < 2:
                    continue

                # Align price histories (shortest wins)
                min_len = min(len(prices1), len(prices2))
                prices1 = prices1[-min_len:]
                prices2 = prices2[-min_len:]

                corr = calculate_correlation(prices1, prices2)
                if corr is not None:
                    correlations.append(corr)

        if not correlations:
            return 0.0

        # Return average correlation (absolute value to flag high correlation regardless of direction)
        avg_corr = sum(abs(c) for c in correlations) / len(correlations)
        return min(avg_corr, 1.0)  # Clamp to 1.0

    def update_state(self, state: PortfolioState) -> None:
        """
        Compute and update PortfolioState.avg_pair_correlation.

        Args:
            state: Current portfolio state
        """
        avg_corr = self.compute_portfolio_correlation(state)
        state.avg_pair_correlation = avg_corr
        
        if avg_corr > 0.8:
            logger.warning(f"High portfolio correlation detected: {avg_corr:.2f}")

    def is_high_correlation(self, state: PortfolioState, threshold: float = 0.8) -> bool:
        """
        Check if portfolio correlation exceeds threshold.

        Args:
            state: Current portfolio state
            threshold: Correlation threshold (default 0.8)

        Returns:
            True if avg correlation > threshold
        """
        return state.avg_pair_correlation > threshold

    def reset(self) -> None:
        """Clear all price histories."""
        self.price_windows.clear()

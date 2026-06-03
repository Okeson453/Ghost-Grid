"""
scoring/hlcp/liquidity_mapper.py
Liquidity void mapper — equal highs/lows as stop clusters.

WHY liquidity matters: institutional algorithms hunt retail stop loss orders
clustered at obvious equal highs (long liquidity) and equal lows (short liquidity).
When price is approaching a liquidity void in the direction of the trade, it has
a "magnetic pull" — higher probability of continuation to capture those stops.

Scoring:
  Void in direction, distance < 1.0 ATR:  20 pts (strong pull)
  Void in direction, distance 1.0–2.0 ATR: 12 pts
  Void in direction, distance 2.0–3.0 ATR:  6 pts
  No void or wrong direction:               0 pts
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from data.schema import OHLCV


EQUAL_LEVEL_TOLERANCE = 0.0003   # 3 pips — levels within this are "equal"
MAX_VOID_DISTANCE_ATR  = 3.0     # Beyond 3 ATR = not "magnetic"


@dataclass(frozen=True)
class LiquidityMap:
    void_nearby:     bool
    direction_match: bool
    nearest_level:   float
    distance_atr:    float


def map_liquidity(
    m5_bars: list[OHLCV],
    current_price: float,
    atr_5m: float,
    direction: str,
) -> LiquidityMap:
    """
    Identify nearest equal high (for LONG) or equal low (for SHORT)
    within MAX_VOID_DISTANCE_ATR of current price.
    """
    if len(m5_bars) < 10 or atr_5m == 0:
        return LiquidityMap(False, False, 0.0, 999.0)

    search = m5_bars[-50:] if len(m5_bars) > 50 else m5_bars

    if direction == "LONG":
        levels = _find_equal_levels([b.high for b in search])
        # We want liquidity ABOVE current price (long stops cluster above highs)
        targets = [l for l in levels if l > current_price]
    else:
        levels = _find_equal_levels([b.low for b in search])
        # We want liquidity BELOW current price (short stops cluster below lows)
        targets = [l for l in levels if l < current_price]

    if not targets:
        return LiquidityMap(False, False, 0.0, 999.0)

    nearest  = min(targets, key=lambda l: abs(l - current_price))
    dist_atr = abs(nearest - current_price) / atr_5m
    nearby   = dist_atr <= MAX_VOID_DISTANCE_ATR
    matches  = (nearest > current_price and direction == "LONG") or \
               (nearest < current_price and direction == "SHORT")

    return LiquidityMap(
        void_nearby=nearby,
        direction_match=matches,
        nearest_level=nearest,
        distance_atr=dist_atr,
    )


def score_liquidity(liq: LiquidityMap) -> int:
    """Convert LiquidityMap to score 0–20."""
    if not liq.void_nearby or not liq.direction_match:
        return 0
    if liq.distance_atr < 1.0:
        return 20
    if liq.distance_atr < 2.0:
        return 12
    if liq.distance_atr < 3.0:
        return 6
    return 0


def _find_equal_levels(
    prices: list[float],
    tolerance: float = EQUAL_LEVEL_TOLERANCE,
) -> list[float]:
    """
    Find price levels that appear ≥2 times within tolerance.
    Returns unique representative level per cluster.
    """
    if not prices:
        return []

    clusters: list[float] = []
    sorted_prices = sorted(prices)

    i = 0
    while i < len(sorted_prices):
        cluster = [sorted_prices[i]]
        j = i + 1
        while j < len(sorted_prices) and abs(sorted_prices[j] - sorted_prices[i]) <= tolerance:
            cluster.append(sorted_prices[j])
            j += 1
        if len(cluster) >= 2:
            # Representative level = average of cluster
            clusters.append(sum(cluster) / len(cluster))
        i = j

    return clusters

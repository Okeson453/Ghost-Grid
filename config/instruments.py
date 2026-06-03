"""
config/instruments.py
Instrument universe — all metadata needed for position sizing and session filtering.
Frozen dataclasses: never mutated at runtime.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    tier: int  # 1=Primary (always), 2=Secondary (session-gated), 3=Optional
    pip_size: float  # 0.0001 for 5-digit, 0.01 for JPY pairs / XAUUSD
    pip_value: float  # USD per pip per 1.0 standard lot
    min_lot: float  # Broker minimum lot size
    lot_step: float  # Lot increment (round DOWN to this)
    max_spread: float  # Max spread in pips — entry blocked if exceeded
    sessions: tuple[str, ...]  # Sessions eligible: "ASIA"|"LONDON"|"NY"|"OVERLAP"

    @property
    def spread_in_price(self) -> float:
        """Convert max_spread pips to price units for comparison with ask-bid."""
        return self.max_spread * self.pip_size


# ──────────────────────────────────────────────────────────────────────────────
# INSTRUMENT REGISTRY
# Source of truth for all instrument metadata.
# Edit here, nowhere else.
# ──────────────────────────────────────────────────────────────────────────────
INSTRUMENTS: dict[str, Instrument] = {
    # ── Tier 1: Primary — trade in all eligible sessions ──────────────────
    "EURUSD": Instrument(
        symbol="EURUSD",
        tier=1,
        pip_size=0.0001,
        pip_value=10.0,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.0,
        sessions=("LONDON", "NY", "OVERLAP"),
    ),
    "GBPUSD": Instrument(
        symbol="GBPUSD",
        tier=1,
        pip_size=0.0001,
        pip_value=10.0,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.5,
        sessions=("LONDON", "NY", "OVERLAP"),
    ),
    "USDJPY": Instrument(
        symbol="USDJPY",
        tier=1,
        pip_size=0.01,
        pip_value=9.09,  # ~$9.09 at USDJPY=110
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.0,
        sessions=("ASIA", "LONDON", "NY", "OVERLAP"),
    ),
    "XAUUSD": Instrument(
        symbol="XAUUSD",
        tier=1,
        pip_size=0.01,
        pip_value=1.0,  # $1 per pip per 1 lot (100 oz)
        min_lot=0.01,
        lot_step=0.01,
        max_spread=30.0,
        sessions=("LONDON", "NY", "OVERLAP"),
    ),
    # ── Tier 2: Secondary — session-gated ─────────────────────────────────
    "GBPJPY": Instrument(
        symbol="GBPJPY",
        tier=2,
        pip_size=0.01,
        pip_value=9.09,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=4.0,
        sessions=("LONDON", "OVERLAP"),
    ),
    "EURJPY": Instrument(
        symbol="EURJPY",
        tier=2,
        pip_size=0.01,
        pip_value=9.09,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=3.0,
        sessions=("LONDON", "OVERLAP"),
    ),
    "AUDUSD": Instrument(
        symbol="AUDUSD",
        tier=2,
        pip_size=0.0001,
        pip_value=10.0,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.5,
        sessions=("ASIA", "LONDON"),
    ),
    "USDCHF": Instrument(
        symbol="USDCHF",
        tier=2,
        pip_size=0.0001,
        pip_value=10.27,  # ~$10.27 at USDCHF=0.975
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.5,
        sessions=("LONDON", "NY", "OVERLAP"),
    ),
    # ── Tier 3: Optional — breakout regime only, H_c ≥ 150 ────────────────
    "US30": Instrument(
        symbol="US30",
        tier=3,
        pip_size=1.0,
        pip_value=1.0,  # $1 per point per 1 lot
        min_lot=0.01,
        lot_step=0.01,
        max_spread=5.0,
        sessions=("NY", "OVERLAP"),
    ),
    "NAS100": Instrument(
        symbol="NAS100",
        tier=3,
        pip_size=1.0,
        pip_value=1.0,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=5.0,
        sessions=("NY", "OVERLAP"),
    ),
    "BTCUSD": Instrument(
        symbol="BTCUSD",
        tier=3,
        pip_size=1.0,
        pip_value=1.0,
        min_lot=0.01,
        lot_step=0.01,
        max_spread=200.0,
        sessions=("LONDON", "NY", "OVERLAP"),
    ),
    "USDCAD": Instrument(
        symbol="USDCAD",
        tier=2,
        pip_size=0.0001,
        pip_value=7.43,  # ~$7.43 at USDCAD=1.345
        min_lot=0.01,
        lot_step=0.01,
        max_spread=2.5,
        sessions=("NY", "OVERLAP"),
    ),
}

# Convenience lookups
TIER1 = {k: v for k, v in INSTRUMENTS.items() if v.tier == 1}
TIER2 = {k: v for k, v in INSTRUMENTS.items() if v.tier == 2}
TIER3 = {k: v for k, v in INSTRUMENTS.items() if v.tier == 3}

ALL_SYMBOLS: list[str] = list(INSTRUMENTS.keys())


def get_instrument(symbol: str) -> Instrument:
    """Raise KeyError with helpful message if symbol not in registry."""
    if symbol not in INSTRUMENTS:
        raise KeyError(
            f"Symbol '{symbol}' not in INSTRUMENTS registry. Available: {ALL_SYMBOLS}"
        )
    return INSTRUMENTS[symbol]

"""
regime/fingerprint.py
Combined regime + session fingerprint.

Called by data/snapshot_builder.py once per MarketSnapshot.
Populates the snap.regime field that was empty ("") in Parts 1–2.

WHY separate from classifier.py:
fingerprint.py owns the EMA ribbon state between snapshots.
classifier.py is a pure function on snapshot data.
This separation makes classifier.py fully unit-testable without state.
"""

from __future__ import annotations
from data.schema import MarketSnapshot
from regime.classifier import classify_regime
from regime.session import detect_session


def get_regime_fingerprint(snap: MarketSnapshot) -> str:
    """
    Returns regime string for the given snapshot.
    Format: "{REGIME}" (e.g. "TREND", "CHOP")
    Session is already in snap.session — not included in regime string.
    """
    return classify_regime(snap)


def annotate_snapshot(snap: MarketSnapshot) -> MarketSnapshot:
    """
    Return a new MarketSnapshot with regime field populated.
    WHY new object: MarketSnapshot is frozen — cannot mutate.
    Creates a copy with regime replaced.
    """
    from dataclasses import replace
    regime = get_regime_fingerprint(snap)
    return replace(snap, regime=regime)

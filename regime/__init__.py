"""
regime/
Market regime classification for GHOST GRID.

Public API:
  classify_regime()     — 4-state regime classifier (TREND|CHOP|BREAKOUT|REVERSAL)
  detect_session()      — Session detector (ASIA|LONDON|NY|OVERLAP|INACTIVE)
  annotate_snapshot()   — Populate snap.regime field
  is_killzone()         — Check if session is high-probability window
"""

from .classifier import classify_regime
from .session import detect_session, is_killzone
from .fingerprint import annotate_snapshot

__all__ = [
    "classify_regime",
    "detect_session",
    "is_killzone",
    "annotate_snapshot",
]

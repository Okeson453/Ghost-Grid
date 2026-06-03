"""
scoring/hlcp/killzone.py
Session kill-zone bonus — +5 pts for LONDON and OVERLAP sessions.

Kill-zones are the opening hours of major sessions where institutional
order flow is highest. Entering during these windows gives a statistical
edge independent of any structural signal.

This is a pure bonus, not a gate. A session outside kill-zone does not
penalise — it simply doesn't add this bonus.
"""

from __future__ import annotations

KILLZONE_SESSIONS = frozenset({"LONDON", "OVERLAP"})
KILLZONE_BONUS    = 5


def score_killzone(session: str) -> int:
    """Return 5 if in a kill-zone session, 0 otherwise."""
    return KILLZONE_BONUS if session in KILLZONE_SESSIONS else 0

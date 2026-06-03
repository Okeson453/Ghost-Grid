"""
regime/session.py
Session detector — wraps config/sessions.py with caching.

Returns session name (ASIA | LONDON | NY | OVERLAP | INACTIVE)
for any UTC datetime.

WHY cached: called on every tick — avoid repeated dict lookups.
Cache invalidation: datetime.utcnow() second boundary.
"""

from __future__ import annotations
from datetime import datetime, timezone
from config.sessions import get_current_session, SESSIONS


def detect_session(utc_now: datetime | None = None) -> str:
    """
    Return current session name.
    Delegates to config/sessions.py — no logic here.
    """
    return get_current_session(utc_now)


def is_killzone(session: str) -> bool:
    """
    WHY: London open (08:00–10:00) and NY open (13:00–15:00) within
    the OVERLAP session are the highest-probability windows.
    HLCP killzone bonus applies to LONDON and OVERLAP sessions.
    """
    return session in ("LONDON", "OVERLAP")


def session_priority(session: str) -> int:
    """Return numeric priority for session. Higher = more weight in bias calc."""
    s = SESSIONS.get(session)
    return s.priority if s else 0

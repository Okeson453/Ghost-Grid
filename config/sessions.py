"""
config/sessions.py
Session window definitions — UTC only.
All times are inclusive start, exclusive end.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import time, datetime, timezone


@dataclass(frozen=True)
class Session:
    name: str
    utc_start: time  # inclusive
    utc_end: time  # exclusive
    priority: int  # Higher = more important for scoring bonus

    def contains(self, utc_time: time) -> bool:
        """WHY: handles the midnight rollover case (e.g. 22:00–02:00)."""
        if self.utc_start <= self.utc_end:
            return self.utc_start <= utc_time < self.utc_end
        # Crosses midnight
        return utc_time >= self.utc_start or utc_time < self.utc_end


SESSIONS: dict[str, Session] = {
    "ASIA": Session(
        name="ASIA",
        utc_start=time(0, 0),
        utc_end=time(8, 0),
        priority=1,
    ),
    "LONDON": Session(
        name="LONDON",
        utc_start=time(8, 0),
        utc_end=time(12, 0),
        priority=3,
    ),
    "OVERLAP": Session(
        name="OVERLAP",
        utc_start=time(12, 0),
        utc_end=time(17, 0),
        priority=4,  # Highest probability — London/NY simultaneous
    ),
    "NY": Session(
        name="NY",
        utc_start=time(17, 0),
        utc_end=time(22, 0),
        priority=2,
    ),
}


def get_current_session(utc_now: datetime | None = None) -> str:
    """
    Returns session name for given UTC time.
    Defaults to datetime.now(UTC) if not supplied.
    Returns "INACTIVE" for 22:00–00:00 UTC (avoid dead-market trading).
    """
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)

    t = utc_now.time()
    for name, session in SESSIONS.items():
        if session.contains(t):
            return name
    return "INACTIVE"

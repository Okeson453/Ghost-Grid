"""
config package public API.
Import from here — never from sub-modules directly.
"""

from .settings import Settings, get_settings
from .instruments import (
    Instrument,
    INSTRUMENTS,
    TIER1,
    TIER2,
    TIER3,
    ALL_SYMBOLS,
    get_instrument,
)
from .sessions import Session, SESSIONS, get_current_session
from .constants import (
    TIMEFRAMES,
    M1_BARS_BUFFER,
    M3_BARS_BUFFER,
    M5_BARS_BUFFER,
    CVD_RING_BUFFER_SIZE,
    SCHMITT_SUSTAIN_CYCLES,
    WATCHLIST_DECAY_BARS,
    REGIME_THRESHOLDS,
    FULL_AUTO_STRONG_BONUS,
    RECONNECT_BACKOFF_BASE_S,
    RECONNECT_BACKOFF_MAX_S,
    RECONNECT_MAX_ATTEMPTS,
    RECONNECT_PAUSE_THRESHOLD,
    PROFIT_TRIGGER_USD,
    TRAIL_FLOOR_USD,
    CVD_EXIT_ZSCORE,
    TICK_PIPE_INTERVAL_MS,
)

__all__ = [
    "Settings",
    "get_settings",
    "Instrument",
    "INSTRUMENTS",
    "TIER1",
    "TIER2",
    "TIER3",
    "ALL_SYMBOLS",
    "get_instrument",
    "Session",
    "SESSIONS",
    "get_current_session",
    "TIMEFRAMES",
    "M1_BARS_BUFFER",
    "M3_BARS_BUFFER",
    "M5_BARS_BUFFER",
    "CVD_RING_BUFFER_SIZE",
    "SCHMITT_SUSTAIN_CYCLES",
    "WATCHLIST_DECAY_BARS",
    "REGIME_THRESHOLDS",
    "FULL_AUTO_STRONG_BONUS",
    "RECONNECT_BACKOFF_BASE_S",
    "RECONNECT_BACKOFF_MAX_S",
    "RECONNECT_MAX_ATTEMPTS",
    "RECONNECT_PAUSE_THRESHOLD",
    "PROFIT_TRIGGER_USD",
    "TRAIL_FLOOR_USD",
    "CVD_EXIT_ZSCORE",
    "TICK_PIPE_INTERVAL_MS",
]

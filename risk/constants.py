"""
risk/constants.py
GHOST GRID RISK KERNEL — IMMUTABLE CONSTANTS.

────────────────────────────────────────────────────────────────
THESE VALUES ARE THE ONLY AUTHORITY ON RISK SIZING AND LIMITS.
NO FUNCTION, CLASS, CONFIG, OR RUNTIME STATE MAY OVERRIDE THEM.
TO CHANGE: edit this file and REDEPLOY. No hot-reload. No env var.
────────────────────────────────────────────────────────────────

WHY hardcoded, not configurable:
If risk limits live in .env or config.json, a misconfigured deploy
or a prompt injection into Telegram could change them. Hardcoded
constants survive any runtime modification attempt.
"""

# Per-trade limits
MAX_RISK_PER_TRADE: float = 0.01  # 1% of net equity per trade
MIN_RR_RATIO: float = 1.5  # Min reward:risk pre-entry (SL vs TP runway)

# Portfolio-level limits
MAX_CONCURRENT: int = 5  # Maximum open positions simultaneously
MAX_BASKET_RISK: float = 0.05  # 5% total portfolio heat
MAX_PORTFOLIO_DRAWDOWN: float = 0.20  # 20% → permanent halt, manual review

# Daily limits (reset at UTC midnight)
MAX_DAILY_LOSS: float = 0.04  # 4% → immediate LOCKOUT + close all
MAX_DAILY_GAIN: float = 0.15  # 15% → halt trading (protect profits)

# Execution limits
MAX_SPREAD_PCT: float = 0.0012  # 0.12% max spread at entry time
MARGIN_BUFFER: float = 0.80  # Never exceed 80% margin utilisation

# Size constraints
MIN_LOT_SIZE: float = 0.01  # Absolute floor regardless of calculation
MAX_LOT_SIZE: float = 10.0  # Absolute ceiling regardless of calculation


def _verify_constants() -> None:
    """
    Sanity check — called at module import.
    Prevents obviously wrong values (e.g., typo sets MAX_DAILY_LOSS=0.40).
    """
    assert 0 < MAX_RISK_PER_TRADE <= 0.05, "MAX_RISK_PER_TRADE out of safe range"
    assert 0 < MAX_DAILY_LOSS <= 0.10, "MAX_DAILY_LOSS out of safe range"
    assert 0 < MAX_DAILY_GAIN <= 0.50, "MAX_DAILY_GAIN out of safe range"
    assert 1 <= MAX_CONCURRENT <= 20, "MAX_CONCURRENT out of range"
    assert 0 < MAX_BASKET_RISK <= 0.20, "MAX_BASKET_RISK out of safe range"
    assert MIN_RR_RATIO >= 1.0, "MIN_RR_RATIO below 1.0 is invalid"


_verify_constants()  # Runs at import — fails fast if constants are wrong

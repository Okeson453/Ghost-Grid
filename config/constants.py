"""
config/constants.py
System constants — tunable between deployments, NOT at runtime.
These control buffer sizes, scoring thresholds, and exit arithmetic.

RISK CONSTANTS ARE NOT HERE. They are in risk/constants.py and are
immutable. Changing risk constants requires a full redeploy.
"""

# ── Data pipeline ──────────────────────────────────────────────────────────
TIMEFRAMES: list[str] = ["M1", "M3", "M5"]

M1_BARS_BUFFER: int = 300  # ~5 hours of 1-minute bars in memory
M3_BARS_BUFFER: int = 200  # ~10 hours of 3-minute bars
M5_BARS_BUFFER: int = 100  # ~8 hours of 5-minute bars

CVD_RING_BUFFER_SIZE: int = 200  # Minutes of CVD history (EMA + Z-score window)
TICK_PIPE_INTERVAL_MS: int = 200  # EA sends tick snapshots every N ms

# ── Scoring engine ─────────────────────────────────────────────────────────
SCHMITT_SUSTAIN_CYCLES: int = 2  # H_c must sustain ≥2 cycles before FULL_AUTO
WATCHLIST_DECAY_BARS: int = 15  # Watchlist entry expires after N scoring cycles

# Regime-adjusted H_c thresholds (gate.py reads these)
# From design: TREND=130, CHOP=155, BREAKOUT=140, REVERSAL=145
REGIME_THRESHOLDS: dict[str, int] = {
    "TREND": 130,  # Most permissive — trends are reliable
    "CHOP": 155,  # Most restrictive — false signals common in ranging markets
    "BREAKOUT": 140,  # Strong but needs extra confirmation
    "REVERSAL": 145,  # High reward but needs full confluence
}
FULL_AUTO_STRONG_BONUS: int = 20  # H_c ≥ threshold + 20 → max allowed size

# ── Reconnection ────────────────────────────────────────────────────────────
RECONNECT_BACKOFF_BASE_S: int = 1  # Start at 1 second
RECONNECT_BACKOFF_MAX_S: int = 30  # Cap at 30 seconds
RECONNECT_MAX_ATTEMPTS: int = 5  # After this many failures, pause all trading
RECONNECT_PAUSE_THRESHOLD: int = 5  # Consecutive failures before pause

# ── Position Exit — Multi-Layer Thresholds ────────────────────────────────────
# Layer 1: Profit trigger → arms trailing stop
PROFIT_TRIGGER_USD: float = 1.50  # Layer 1: $1.50 unrealised profit → trail armed
# Layer 2: Trailing stop execution
TRAIL_FLOOR_USD: float = (
    0.75  # Min trail distance floor: $0.75 (ATR-adaptive usually larger)
)
# Layer 3: Weakness detection (RSI + engulfing + volume cliff all three)
# Layer 4: CVD divergence override (fastest exit)
CVD_EXIT_ZSCORE: float = 2.0  # Close if CVD divergence exceeds 2.0 sigma (Z-score)

# ── Nuclear Portfolio Guardian — 7 Triggers ─────────────────────────────────
# From design: triggers evaluate every 500ms, any fire closes all positions
NUCLEAR_COMBINED_PROFIT_USD: float = 10.00  # Trigger 1: profit ceiling
NUCLEAR_LOSS_PROTECTION_USD: float = -6.00  # Trigger 3: floating loss floor
NUCLEAR_LATENCY_THRESHOLD_MS: float = 500.0  # Trigger 6: execution latency anomaly
NUCLEAR_CORRELATION_SPIKE: float = 0.80  # Trigger 7: avg pair correlation ceiling

# ── Drift detection / backtest baseline (observability) ────────────────
# Expected backtest win rate (percent) used by DriftDetector. This value
# may be updated between deployments but is the single source of truth
# for drift detection thresholds.
BACKTEST_WIN_RATE_PERCENT: float = 58.0
DRIFT_THRESHOLD_PERCENT: float = 8.0
DRIFT_LOOKBACK_TRADES: int = 20

"""
scoring/gate.py
Schmitt-trigger hysteresis gate — prevents false signal fires.

SOURCE: GHOST-GRID-MT5-Design.md § III.2 Schmitt Hysteresis Gate

WHY Schmitt hysteresis:
A single high H_c score can result from momentary data alignment —
one anomalous tick that inflates CVD Z-score or moves price briefly
beyond a BOS level. Without hysteresis, the system would fire on noise.

Requiring N=2 consecutive cycles above threshold ensures the signal
is persistent and not a single-bar artefact.

Per-symbol state tracking:
  - consecutive_above_threshold counter (incremented each H_c ≥ threshold)
  - Reset to 0 the moment H_c drops below threshold
  - FULL_AUTO fires when counter reaches SCHMITT_SUSTAIN_CYCLES (2)

Regime-adjusted thresholds (config/constants.py REGIME_THRESHOLDS):
  - TREND: 130 (reliable trend strength)
  - CHOP: 155 (conservative choppy market)
  - BREAKOUT: 140 (structure break confirmation)
  - REVERSAL: 145 (momentum reversal)

Gate decisions output:
  - DISCARD: H_c below threshold - 20
  - WATCHLIST: H_c within threshold band
  - ALERT: 1st cycle above (Telegram notification only)
  - FULL_AUTO: ≥2 consecutive cycles at threshold (execute order)
  - FULL_AUTO_STRONG: ≥2 cycles at threshold + 20 (max size allowed)
"""

from __future__ import annotations
import logging
from scoring.models import ConfluenceScore, GateDecision
from config.constants import (
    REGIME_THRESHOLDS,
    SCHMITT_SUSTAIN_CYCLES,
    FULL_AUTO_STRONG_BONUS,
    WATCHLIST_DECAY_BARS,
)

logger = logging.getLogger(__name__)


class ConfluenceGate:
    """
    Per-symbol Schmitt hysteresis gate.

    One instance manages ALL symbols (keyed dict).
    Not shared across asyncio tasks — one gate per scoring pipeline.
    """

    def __init__(self) -> None:
        # symbol → consecutive cycles above threshold
        self._consecutive: dict[str, int] = {}
        # symbol → cycles since last alert sent (prevents alert spam)
        self._alert_cooldown: dict[str, int] = {}
        # symbol → watchlist decay counter
        self._watchlist_decay: dict[str, int] = {}

    def evaluate(
        self,
        score: ConfluenceScore,
    ) -> GateDecision:
        """
        Evaluate one ConfluenceScore and return a gate decision.

        Args:
            score: ConfluenceScore from scoring/fusion.py

        Returns:
            GateDecision enum value
        """
        sym = score.symbol

        # Get regime-adjusted threshold
        threshold = REGIME_THRESHOLDS.get(score.regime, 140)
        composite = score.composite

        # ── Update consecutive counter ─────────────────────────────────
        if composite >= threshold:
            self._consecutive[sym] = self._consecutive.get(sym, 0) + 1
            self._watchlist_decay.pop(sym, None)  # Clear watchlist decay
        else:
            self._consecutive[sym] = 0

        consecutive = self._consecutive.get(sym, 0)

        # ── Decision tree ──────────────────────────────────────────────
        # FULL_AUTO_STRONG: sustained + well above threshold
        if (
            consecutive >= SCHMITT_SUSTAIN_CYCLES
            and composite >= threshold + FULL_AUTO_STRONG_BONUS
        ):
            self._reset_alert_cooldown(sym)
            return GateDecision.FULL_AUTO_STRONG

        # FULL_AUTO: sustained above threshold
        if consecutive >= SCHMITT_SUSTAIN_CYCLES and composite >= threshold:
            self._reset_alert_cooldown(sym)
            return GateDecision.FULL_AUTO

        # ALERT: first cycle above threshold (Telegram notification, no execution)
        if consecutive == 1 and composite >= threshold:
            cooldown = self._alert_cooldown.get(sym, 0)
            if cooldown == 0:
                self._alert_cooldown[sym] = 10  # 10-cycle cooldown before next alert
                return GateDecision.ALERT
            else:
                self._alert_cooldown[sym] = max(0, cooldown - 1)
                return GateDecision.DISCARD  # In cooldown — suppress alert

        # WATCHLIST: approaching threshold (within threshold - 20)
        if composite >= threshold - 20:
            self._watchlist_decay[sym] = self._watchlist_decay.get(sym, 0) + 1
            if self._watchlist_decay.get(sym, 0) <= WATCHLIST_DECAY_BARS:
                return GateDecision.WATCHLIST
            # Watchlist expired
            self._watchlist_decay.pop(sym, None)

        return GateDecision.DISCARD

    def reset(self, symbol: str) -> None:
        """
        Hard reset all state for a symbol.
        Called after a position is opened or nuclear fires.
        WHY: after an entry or nuclear exit, the signal episode is over.
        Resetting prevents immediate re-entry on stale cycle counts.
        """
        self._consecutive.pop(symbol, None)
        self._alert_cooldown.pop(symbol, None)
        self._watchlist_decay.pop(symbol, None)

    def _reset_alert_cooldown(self, sym: str) -> None:
        self._alert_cooldown.pop(sym, None)

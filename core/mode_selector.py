"""
core/mode_selector.py
Mode-aware accessors for mode-specific thresholds (profit trigger, trail floor).

This centralizes mode → numeric mappings so the rest of the code can
request the correct threshold for the current `PortfolioState.current_mode`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from config import constants as cfg
from observability.drift_detector import check_drift
from portfolio.state import PortfolioState


def get_profit_trigger_for_mode(mode: Optional[str]) -> float:
    """Return profit trigger USD for given mode."""
    if mode == "SCALP_BURST":
        return 3.00
    return cfg.PROFIT_TRIGGER_USD


def get_trail_floor_for_mode(mode: Optional[str]) -> float:
    """Return trailing-floor USD for given mode."""
    if mode == "SCALP_BURST":
        return 1.50
    return cfg.TRAIL_FLOOR_USD


@dataclass(frozen=True)
class ModeSelection:
    mode: str
    reason: str


class ModeSelector:
    """Select a portfolio mode based on market regime, session, and drift."""

    def __init__(self) -> None:
        self._last_reason: str | None = None

    def evaluate(self, snapshot: Any, portfolio: PortfolioState) -> str:
        regime = str(getattr(snapshot, "regime", "")).upper()
        session = str(getattr(snapshot, "session", "")).upper()

        drift = check_drift(lookback=20)
        drift_pressure = drift.drifted or (drift.live_wr < 45.0)

        if regime == "CHOP" and drift_pressure:
            self._last_reason = "Drift detector indicates weak performance in chop"
            return "DAILY_TARGET"

        if regime == "TREND" and session in {"LONDON", "NEW_YORK"}:
            self._last_reason = "Trending market with healthy drift profile"
            return "SCALP_BURST"

        if portfolio.current_mode in {"SCALP_BURST", "AGGRESSIVE_COMPOUNDING", "DAILY_TARGET"}:
            self._last_reason = "Maintaining prior selected mode"
            return portfolio.current_mode

        self._last_reason = "Defaulting to scalp burst"
        return "SCALP_BURST"

    def apply(self, snapshot: Any, portfolio: PortfolioState) -> str:
        mode = self.evaluate(snapshot, portfolio)
        if portfolio.current_mode != mode:
            portfolio.current_mode = mode
        return mode

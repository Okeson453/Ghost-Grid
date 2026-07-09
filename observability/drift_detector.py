"""
observability/drift_detector.py
Live vs. backtest drift detection.

Compares rolling win rate from live trades against backtest expectation.
If live win rate falls below (backtest_wr - 8%), triggers a drift alert.

WHY: Statistical guardrail. If actual performance diverges significantly
from validated backtest, the system may have found a regime shift or the
trader's expectations were unrealistic. Alert enables manual review.

Backtest baseline: configured in config/constants.py (future) or
hardcoded here for now as BACKTEST_WIN_RATE_PERCENT.
"""

from __future__ import annotations
import csv
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Configurable backtest baseline ─────────────────────────────────────
from config.constants import (
    BACKTEST_WIN_RATE_PERCENT,
    DRIFT_THRESHOLD_PERCENT,
    DRIFT_LOOKBACK_TRADES,
)


@dataclass(frozen=True)
class DriftAlert:
    """Drift detection result."""

    drifted: bool
    backtest_wr: float
    live_wr: float
    threshold_wr: float
    trades_evaluated: int
    message: str


class DriftDetector:
    """
    Stateless drift detector — reads from trade journal CSV and computes
    rolling win rate vs. backtest baseline.
    """

    def __init__(
        self,
        trades_csv: Optional[str] = None,
        backtest_wr: float = BACKTEST_WIN_RATE_PERCENT,
        drift_threshold: float = DRIFT_THRESHOLD_PERCENT,
        lookback_trades: int = DRIFT_LOOKBACK_TRADES,
    ) -> None:
        if trades_csv is None:
            trades_csv = "./data_store/trades.csv"
        self.trades_csv = Path(trades_csv)
        self.backtest_wr = backtest_wr
        self.drift_threshold = drift_threshold
        self.lookback_trades = lookback_trades

    def compute_win_rate(self, lookback: int | None = None) -> Optional[float]:
        """
        Compute win rate from last N closed trades in trade journal.
        Returns None if insufficient trades exist.

        Win rate = (# profitable trades) / (# total trades)
        """
        if not self.trades_csv.exists():
            return None

        closed_trades = []
        try:
            with open(self.trades_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Only count rows with exit data (closed trades)
                    if row.get("exit_price") and row.get("pnl_usd"):
                        try:
                            pnl = float(row["pnl_usd"])
                            closed_trades.append(pnl)
                        except (ValueError, KeyError):
                            continue
        except Exception as e:
            logger.error(f"Failed to read trade journal: {e}")
            return None

        if not closed_trades:
            return None

        # Determine lookback to use
        if lookback is None:
            lookback = self.lookback_trades

        # Use last N trades
        recent_trades = (
            closed_trades[-lookback:]
            if len(closed_trades) > lookback
            else closed_trades
        )

        wins = sum(1 for pnl in recent_trades if pnl > 0)
        total = len(recent_trades)

        return (wins / total * 100.0) if total > 0 else None

    def check_drift(self, lookback: int | None = None) -> DriftAlert:
        """
        Evaluate live win rate vs. backtest baseline.

        Returns:
            DriftAlert with drifted=True if live_wr < (backtest_wr - threshold)
        """
        live_wr = self.compute_win_rate(lookback)

        if live_wr is None:
            return DriftAlert(
                drifted=False,
                backtest_wr=self.backtest_wr,
                live_wr=0.0,
                threshold_wr=self.backtest_wr - self.drift_threshold,
                trades_evaluated=0,
                message="Insufficient closed trades to evaluate drift.",
            )

        threshold = self.backtest_wr - self.drift_threshold

        # Count total trades evaluated
        total_trades = self._count_closed_trades()

        actual_lookback = lookback if lookback is not None else self.lookback_trades

        if live_wr < threshold:
            message = (
                f"DRIFT DETECTED: Live win rate {live_wr:.1f}% < "
                f"threshold {threshold:.1f}% (backtest {self.backtest_wr:.1f}% - "
                f"{self.drift_threshold:.1f}% buffer). Last {actual_lookback} trades."
            )
            return DriftAlert(
                drifted=True,
                backtest_wr=self.backtest_wr,
                live_wr=live_wr,
                threshold_wr=threshold,
                trades_evaluated=total_trades,
                message=message,
            )
        else:
            message = (
                f"Win rate OK: {live_wr:.1f}% >= threshold {threshold:.1f}%. "
                f"Backtest {self.backtest_wr:.1f}%."
            )
            return DriftAlert(
                drifted=False,
                backtest_wr=self.backtest_wr,
                live_wr=live_wr,
                threshold_wr=threshold,
                trades_evaluated=total_trades,
                message=message,
            )

    def _count_closed_trades(self) -> int:
        """Count total closed trades in journal."""
        if not self.trades_csv.exists():
            return 0

        count = 0
        try:
            with open(self.trades_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("exit_price"):
                        count += 1
        except Exception:
            pass

        return count


# ── Global singleton instance ──────────────────────────────────────────

_detector: Optional[DriftDetector] = None


def get_detector() -> DriftDetector:
    """Get or create the global DriftDetector instance."""
    global _detector
    if _detector is None:
        _detector = DriftDetector(
            backtest_wr=BACKTEST_WIN_RATE_PERCENT,
            drift_threshold=DRIFT_THRESHOLD_PERCENT,
        )
    return _detector


def compute_win_rate(lookback: int | None = None) -> Optional[float]:
    """Compute live win rate from the global drift detector."""
    return get_detector().compute_win_rate(lookback)


def check_drift(lookback: int | None = None) -> DriftAlert:
    """
    Check for statistical drift between live and backtest performance.
    Convenience wrapper.
    """
    alert = get_detector().check_drift(lookback)
    if alert.drifted:
        logger.warning(alert.message)
    else:
        logger.info(alert.message)
    return alert

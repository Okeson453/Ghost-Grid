"""
observability/daily_report.py
End-of-day summary report generator.

Called at UTC midnight (or manually via scripts/stop.py).
Generates a structured report with:
  - Daily P&L (realized + unrealised)
  - Win rate and trade count
  - Max drawdown intraday
  - H_c score distribution
  - Regime breakdown
  - Drift check result
  - Portfolio state snapshot

Report is returned as a dict + JSON, pushed to Telegram and appended
to daily_reports.csv for historical analysis.

WHY: Enables daily trader review without logging into VPS.
Doubles as compliance record.
"""

from __future__ import annotations
import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
    """Complete daily report snapshot."""

    date_utc: str  # YYYY-MM-DD format
    summary: Dict[str, Any]  # Main KPIs
    pnl: Dict[str, Any]  # P&L breakdown
    trades: Dict[str, Any]  # Trade statistics
    scoring: Dict[str, Any]  # H_c distribution
    drift: Dict[str, Any]  # Drift check result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_telegram_message(self) -> str:
        """Format report as Telegram message."""
        lines = [
            f"📊 *GHOST GRID Daily Report — {self.date_utc}*",
            "",
            "🎯 **Summary**",
            f"Status: {self.summary.get('status', 'N/A')}",
            f"Starting Equity: ${self.summary.get('starting_equity', 0):.2f}",
            f"Ending Equity: ${self.summary.get('ending_equity', 0):.2f}",
            "",
            "💰 **P&L**",
            f"Realized: ${self.pnl.get('realized_pnl', 0):.2f}",
            f"Unrealised: ${self.pnl.get('unrealized_pnl', 0):.2f}",
            f"Daily Total: ${self.pnl.get('daily_total', 0):.2f}",
            f"Daily Return: {self.pnl.get('daily_return_pct', 0):.2f}%",
            "",
            "📈 **Trades**",
            f"Closed: {self.trades.get('closed_count', 0)}",
            f"Open: {self.trades.get('open_count', 0)}",
            f"Win Rate: {self.trades.get('win_rate_pct', 0):.1f}%",
            f"Avg Win: ${self.trades.get('avg_win_usd', 0):.2f}",
            f"Avg Loss: ${self.trades.get('avg_loss_usd', 0):.2f}",
            f"Profit Factor: {self.trades.get('profit_factor', 0):.2f}",
            "",
            "🎲 **Scoring**",
            f"Signals Fired: {self.scoring.get('signals_fired', 0)}",
            f"Avg H_c: {self.scoring.get('avg_hc', 0):.1f}",
            f"Max H_c: {self.scoring.get('max_hc', 0)}",
            f"Regime: {self.scoring.get('primary_regime', 'N/A')}",
            "",
            "⚠️ **Alerts**",
            f"Drift: {self.drift.get('status', 'OK')}",
            f"Nuclear Events: {self.summary.get('nuclear_count', 0)}",
        ]
        return "\n".join(lines)


class DailyReporter:
    """
    Generates end-of-day reports by aggregating metrics, trades, and
    portfolio state across the session.
    """

    def __init__(
        self,
        metrics_csv: Optional[str] = None,
        trades_csv: Optional[str] = None,
        reports_csv: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> None:
        if output_dir is not None:
            base_dir = Path(output_dir)
            metrics_csv = str(base_dir / "metrics.csv")
            trades_csv = str(base_dir / "trades.csv")
            reports_csv = str(base_dir / "daily_reports.csv")

        self.metrics_csv = Path(metrics_csv or "./data_store/metrics.csv")
        self.trades_csv = Path(trades_csv or "./data_store/trades.csv")
        self.reports_csv = Path(reports_csv or "./data_store/daily_reports.csv")
        self._ensure_reports_file()

    def _ensure_reports_file(self) -> None:
        """Create reports CSV with headers if needed."""
        if self.reports_csv.exists():
            return

        self.reports_csv.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "date_utc",
            "starting_equity",
            "ending_equity",
            "realized_pnl",
            "unrealized_pnl",
            "daily_total_pnl",
            "daily_return_pct",
            "closed_trades",
            "open_trades",
            "win_rate_pct",
            "avg_win_usd",
            "avg_loss_usd",
            "profit_factor",
            "avg_hc",
            "max_hc",
            "primary_regime",
            "signals_fired",
            "nuclear_count",
            "drift_status",
            "report_json",
        ]

        with open(self.reports_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

    def generate_report(
        self,
        starting_equity: float,
        ending_equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        open_position_count: int,
        nuclear_count: int,
        drift_status: str,
    ) -> DailyReport:
        """
        Generate complete daily report.

        Args:
            starting_equity: Starting balance (UTC midnight)
            ending_equity: Current balance
            realized_pnl: Closed trades P&L
            unrealized_pnl: Open positions P&L
            open_position_count: # of open positions
            nuclear_count: # of nuclear events fired today
            drift_status: Result of drift check ("OK" | "ALERT")

        Returns:
            DailyReport with all aggregated data
        """
        now_utc = datetime.utcnow()
        date_utc = now_utc.strftime("%Y-%m-%d")

        daily_total = realized_pnl + unrealized_pnl
        daily_return = (
            (daily_total / starting_equity * 100) if starting_equity > 0 else 0
        )

        # Aggregate trade statistics
        trade_stats = self._compute_trade_stats()
        closed_count = trade_stats["closed_count"]
        win_rate = trade_stats["win_rate_pct"]
        avg_win = trade_stats["avg_win_usd"]
        avg_loss = trade_stats["avg_loss_usd"]
        profit_factor = trade_stats["profit_factor"]

        # Aggregate scoring statistics
        score_stats = self._compute_score_stats()
        avg_hc = score_stats["avg_hc"]
        max_hc = score_stats["max_hc"]
        primary_regime = score_stats["primary_regime"]
        signals_fired = score_stats["signals_fired"]
        regime_breakdown = score_stats.get("regime_breakdown", {})

        report = DailyReport(
            date_utc=date_utc,
            summary={
                "status": "ACTIVE",
                "starting_equity": starting_equity,
                "ending_equity": ending_equity,
                "nuclear_count": nuclear_count,
            },
            pnl={
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "daily_total": daily_total,
                "daily_return_pct": daily_return,
            },
            trades={
                "closed_count": closed_count,
                "open_count": open_position_count,
                "win_rate_pct": win_rate,
                "avg_win_usd": avg_win,
                "avg_loss_usd": avg_loss,
                "profit_factor": profit_factor,
            },
            scoring={
                "signals_fired": signals_fired,
                "avg_hc": avg_hc,
                "max_hc": max_hc,
                "primary_regime": primary_regime,
                "regime_breakdown": regime_breakdown,
            },
            drift={
                "status": drift_status,
            },
        )

        self._append_report(report)
        return report

    def _compute_trade_stats(self) -> Dict[str, Any]:
        """Read trades CSV and compute statistics."""
        if not self.trades_csv.exists():
            return {
                "closed_count": 0,
                "win_rate_pct": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
                "profit_factor": 0.0,
            }

        closed_trades = []
        try:
            with open(self.trades_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("exit_price"):
                        try:
                            pnl = float(row.get("pnl_usd", 0))
                            closed_trades.append(pnl)
                        except ValueError:
                            continue
        except Exception as e:
            logger.error(f"Failed to read trades: {e}")
            return {
                "closed_count": 0,
                "win_rate_pct": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
                "profit_factor": 0.0,
            }

        if not closed_trades:
            return {
                "closed_count": 0,
                "win_rate_pct": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
                "profit_factor": 0.0,
            }

        wins = [p for p in closed_trades if p > 0]
        losses = [p for p in closed_trades if p < 0]
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        profit_factor = (
            sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0.0
        )

        return {
            "closed_count": len(closed_trades),
            "win_rate_pct": win_rate,
            "avg_win_usd": avg_win,
            "avg_loss_usd": abs(avg_loss),
            "profit_factor": profit_factor,
        }

    def _compute_score_stats(self) -> Dict[str, Any]:
        """Read metrics CSV and compute H_c statistics."""
        if not self.metrics_csv.exists():
            return {
                "avg_hc": 0.0,
                "max_hc": 0,
                "primary_regime": "UNKNOWN",
                "signals_fired": 0,
            }

        composites = []
        regimes = {}
        gate_decisions = {}

        try:
            with open(self.metrics_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip rows without H_c scores
                    if not row.get("composite_score"):
                        continue

                    try:
                        composite = float(row["composite_score"])
                        composites.append(composite)

                        regime = row.get("regime", "UNKNOWN")
                        regimes[regime] = regimes.get(regime, 0) + 1

                        gate = row.get("gate_decision", "")
                        if gate:
                            gate_decisions[gate] = gate_decisions.get(gate, 0) + 1
                    except ValueError:
                        continue
        except Exception as e:
            logger.error(f"Failed to read metrics: {e}")
            return {
                "avg_hc": 0.0,
                "max_hc": 0,
                "primary_regime": "UNKNOWN",
                "signals_fired": 0,
            }

        if not composites:
            return {
                "avg_hc": 0.0,
                "max_hc": 0,
                "primary_regime": "UNKNOWN",
                "regime_breakdown": {},
                "signals_fired": 0,
            }

        avg_hc = sum(composites) / len(composites)
        max_hc = max(composites)
        primary_regime = max(regimes, key=regimes.get) if regimes else "UNKNOWN"
        signals_fired = gate_decisions.get("FULL_AUTO", 0) + gate_decisions.get(
            "FULL_AUTO_STRONG", 0
        )

        return {
            "avg_hc": avg_hc,
            "max_hc": int(max_hc),
            "primary_regime": primary_regime,
            "regime_breakdown": regimes,
            "signals_fired": signals_fired,
        }

    def _append_report(self, report: DailyReport) -> None:
        """Append report row to CSV."""
        trade_stats = self._compute_trade_stats()
        score_stats = self._compute_score_stats()

        row = {
            "date_utc": report.date_utc,
            "starting_equity": report.summary.get("starting_equity", 0),
            "ending_equity": report.summary.get("ending_equity", 0),
            "realized_pnl": report.pnl.get("realized_pnl", 0),
            "unrealized_pnl": report.pnl.get("unrealized_pnl", 0),
            "daily_total_pnl": report.pnl.get("daily_total", 0),
            "daily_return_pct": report.pnl.get("daily_return_pct", 0),
            "closed_trades": report.trades.get("closed_count", 0),
            "open_trades": report.trades.get("open_count", 0),
            "win_rate_pct": report.trades.get("win_rate_pct", 0),
            "avg_win_usd": report.trades.get("avg_win_usd", 0),
            "avg_loss_usd": report.trades.get("avg_loss_usd", 0),
            "profit_factor": report.trades.get("profit_factor", 0),
            "avg_hc": report.scoring.get("avg_hc", 0),
            "max_hc": report.scoring.get("max_hc", 0),
            "primary_regime": report.scoring.get("primary_regime", "N/A"),
            "signals_fired": report.scoring.get("signals_fired", 0),
            "nuclear_count": report.summary.get("nuclear_count", 0),
            "drift_status": report.drift.get("status", "UNKNOWN"),
            "report_json": report.to_json(),
        }

        with open(self.reports_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

        logger.info(f"Daily report saved: {report.date_utc}")


# ── Global singleton instance ──────────────────────────────────────────

_reporter: Optional[DailyReporter] = None


def get_reporter() -> DailyReporter:
    """Get or create the global DailyReporter instance."""
    global _reporter
    if _reporter is None:
        _reporter = DailyReporter()
    return _reporter


def generate_daily_report(
    starting_equity: float,
    ending_equity: float,
    realized_pnl: float,
    unrealized_pnl: float,
    open_position_count: int,
    nuclear_count: int,
    drift_status: str,
) -> DailyReport:
    """
    Generate end-of-day report. Convenience wrapper.
    """
    return get_reporter().generate_report(
        starting_equity,
        ending_equity,
        realized_pnl,
        unrealized_pnl,
        open_position_count,
        nuclear_count,
        drift_status,
    )

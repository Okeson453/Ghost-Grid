from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Dict, Optional


class BayesianWeightUpdater:
    """Persist rolling Bayesian weights for HMP/HLCP/MPP strategies."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or os.getenv("GHOSTGRID_DB_PATH", "./data_store/ghost_grid.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_weights (
                    strategy TEXT PRIMARY KEY,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    alpha REAL NOT NULL DEFAULT 1.0,
                    beta REAL NOT NULL DEFAULT 1.0
                )
                """
            )
            conn.commit()

    def update(self, strategy: str, won: bool) -> None:
        strategy = strategy.upper()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT wins, losses, alpha, beta FROM strategy_weights WHERE strategy = ?",
                (strategy,),
            ).fetchone()
            if row is None:
                wins, losses, alpha, beta = 0, 0, 1.0, 1.0
            else:
                wins, losses, alpha, beta = row
            if won:
                wins += 1
                alpha += 1.0
            else:
                losses += 1
                beta += 1.0
            conn.execute(
                """
                INSERT INTO strategy_weights(strategy, wins, losses, alpha, beta)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(strategy) DO UPDATE SET
                    wins=excluded.wins,
                    losses=excluded.losses,
                    alpha=excluded.alpha,
                    beta=excluded.beta
                """,
                (strategy, wins, losses, alpha, beta),
            )
            conn.commit()

    def get_normalized_weights(self) -> Dict[str, float]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT strategy, alpha, beta FROM strategy_weights ORDER BY strategy"
            ).fetchall()
        rows = {row[0]: (float(row[1]), float(row[2])) for row in rows}
        strategies = ["HMP", "HLCP", "MPP"]
        weights: Dict[str, float] = {}
        totals = 0.0
        for strategy in strategies:
            alpha, beta = rows.get(strategy, (1.0, 1.0))
            weight = alpha / (alpha + beta)
            weights[strategy] = weight
            totals += weight
        if totals <= 0.0:
            return {s: 1.0 / len(strategies) for s in strategies}
        return {s: weights[s] / totals for s in strategies}

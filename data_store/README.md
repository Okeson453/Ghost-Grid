# data_store — Dataset Curation & Artifact Management

Per GHOST-GRID-MT5-Design.md § VIII & XIV:

This directory is the **single source of truth for all trading artifacts and curated datasets** used for evaluation, backtesting, and Phase 2+ ML dataset curation.

## Directory Structure

### `datasets/`
Curated datasets for model training and evaluation (Phase 2+).

**Purpose:**
- Versioned trade datasets extracted from live SQLite event log
- Feature-engineered input sets for XGBoost/PyTorch models
- Labeled outputs (win/loss, PnL, exit reason)
- Temporal splits for walk-forward validation

**Structure:**
```
datasets/v1.0/
  - train_2026_06_to_08.parquet     # June-August 2026 training set
  - val_2026_09.parquet              # September 2026 validation
  - test_2026_10.parquet             # October 2026 test (live forward pass)
  - features_schema.json             # Feature definitions
  - labels_schema.json               # Label definitions
```

### `traces/`
Full execution traces for forensic analysis, debugging, and strategy replay.

**Purpose:**
- Tick-level trace files (one per trading day)
- Scoring intermediate results (HMP/HLCP/MPP scores per signal)
- Order dispatch and fill records
- Position state transitions
- Nuclear trigger events

**Structure:**
```
traces/2026_06_03/
  - ticks.jsonl              # 1 tick record per line (symbol, price, CVD, ...)
  - scores.jsonl             # H_c scores (HMP, HLCP, MPP, regime, decision)
  - orders.jsonl             # Order dispatch + fill records
  - positions.jsonl          # Position state transitions
  - nuclear_events.jsonl     # Any nuclear triggers fired today
```

### `signals/`
Historical H_c signals and regime classifications (daily snapshots).

**Purpose:**
- Daily snapshot of all signals fired
- Regime changes and session transitions
- CVD divergence events (Z-score > 2.0)
- Entry/exit signal alignment analysis

**Structure:**
```
signals/2026/
  06/
    03_eurusd_signals.csv    # 2026-06-03 EURUSD signals
    03_eurusd_regimes.csv    # 2026-06-03 EURUSD regime changes
  07/
    ...
```

### `performance/`
Trade performance summaries and metrics aggregation.

**Purpose:**
- Daily P&L reports
- Win rate and PnL distribution by instrument/session/regime
- Drawdown curves
- Win/loss statistics by entry regime and H_c score band

**Structure:**
```
performance/daily/
  - 2026_06_03.json          # Daily summary (equity, trades, PnL)
  - 2026_06_04.json
performance/monthly/
  - 2026_06_summary.json
performance/regime_analysis/
  - performance_by_regime.json
  - performance_by_session.json
  - performance_by_score_band.json
```

## Data Pipeline

### Trace Generation (Real-Time)
SQLite event log → daily_trace_export.py → traces/{date}/*.jsonl

### Dataset Curation (Post-Live, Phase 2)
- Extract trades from sqlite.positions table
- Feature engineering: indicators, regime, session, entry_signal
- Temporal splits: train/val/test by date
- Save as parquet for fast ML ingestion

### Performance Analysis (Daily)
- Aggregate positions table → daily_stats.json
- Compute regime/session/score_band distributions
- Update equity curve

## Retention Policy

- **Traces:** Keep 90 days rolling (auto-delete older)
- **Datasets:** Keep indefinitely (versioned by date range)
- **Signals:** Keep 365 days
- **Performance:** Keep indefinitely

## Automation

Scripts in `scripts/data_store/`:
- `export_daily_trace.py` — runs at UTC midnight, exports previous day
- `curate_dataset.py` — runs monthly, creates ML training set
- `compute_performance_summary.py` — runs daily, updates perf metrics

## Design Rationale

**WHY separate data_store directory:**
- Isolates data artifacts from code
- Enables version control of datasets (git-lfs for parquet files)
- Single source of truth for metrics and backtesting
- Supports Phase 2 ML pipeline without code changes

**WHY JSONL for traces:**
- Streaming append-only format
- Each line is a complete record (no corruption on partial write)
- Easy to parse and filter with standard tools
- Timestamp per record for replay capability

**WHY per-date directory structure:**
- Fast lookup by date
- Enables parallel processing of multiple days
- Natural alignment with UTC midnight resets

---

*Last updated: 2026-07-09 per GHOST-GRID-MT5-Design.md*

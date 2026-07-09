# signals/

Historical H_c signals and regime classifications (daily snapshots).

Directory structure: YYYY/MM/

Each day contains CSV files:
- `DD_SYMBOL_signals.csv` — all H_c signals for that symbol that day
- `DD_SYMBOL_regimes.csv` — regime changes for that symbol

Generated daily by `scripts/data_store/curate_signals.py`.

Used for:
- Signal timing and confluence analysis
- Regime classification validation
- Entry/exit alignment studies

See ../README.md for full documentation.

# traces/

Daily execution traces for forensic analysis and strategy replay.

Each date subdirectory (YYYY/MM/DD) contains JSONL files:
- `ticks.jsonl` — tick-level market data
- `scores.jsonl` — H_c scoring results (HMP/HLCP/MPP)
- `orders.jsonl` — order dispatch and fills
- `positions.jsonl` — position state transitions
- `nuclear_events.jsonl` — nuclear triggers

Generated daily by `scripts/data_store/export_daily_trace.py` at UTC midnight.

Each line is a complete JSON record (append-only, crash-safe).

See ../README.md for full documentation.

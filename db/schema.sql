-- GHOST-GRID Master Schema
-- WHY: Single source of truth for all domain objects: positions, trades, signals, metrics
-- Tables are designed for append-only writes (no DELETE, minimal UPDATE)

-- ──────────────────────────────────────────────────────────────────────────────
-- Positions: Active/closed positions
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity & State
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'CLOSED')) DEFAULT 'OPEN',
    
    -- Entry
    entry_price REAL NOT NULL,
    entry_time_utc TEXT NOT NULL,  -- ISO format: 2026-06-03T14:30:00Z
    entry_bar_id INTEGER NOT NULL,  -- M1 bar ordinal (increments each minute)
    entry_session TEXT NOT NULL,  -- ASIA|LONDON|OVERLAP|NY
    
    -- Size & Risk
    lot_size REAL NOT NULL,
    pip_size REAL NOT NULL,
    pip_value REAL NOT NULL,
    risk_usd REAL,  -- Initial risk amount for position sizing
    
    -- Signal Context
    h_c_entry INTEGER NOT NULL,  -- Histogram value at entry
    regime_entry TEXT NOT NULL,  -- TREND|CHOP|BREAKOUT|REVERSAL
    confluence_score INTEGER,  -- Number of confirmations at entry
    
    -- Exit
    exit_price REAL,
    exit_time_utc TEXT,
    exit_bar_id INTEGER,
    exit_session TEXT,
    exit_reason TEXT CHECK (exit_reason IN (
        'PROFIT_TARGET',
        'STOP_LOSS',
        'CVD_DIVERGENCE',
        'MANUAL_CLOSE',
        'FORCED_CLOSE',
        NULL
    )),
    
    -- P&L
    pnl_usd REAL,
    pnl_pips REAL,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, entry_time_utc)
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_state ON positions(state);
CREATE INDEX idx_positions_created_at ON positions(created_at);


-- ──────────────────────────────────────────────────────────────────────────────
-- Signals: HMA histogram signals and regime changes
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'H_C_PEAK',
        'H_C_TROUGH',
        'REGIME_CHANGE',
        'CVD_DIVERGENCE',
        'CONFLUENCE'
    )),
    
    -- Timing
    bar_id INTEGER NOT NULL,
    signal_time_utc TEXT NOT NULL,
    session TEXT NOT NULL,
    
    -- Values
    h_c_value INTEGER,
    regime_from TEXT,
    regime_to TEXT,
    cvd_zscore REAL,
    confluence_count INTEGER,
    
    -- Severity (for CVD divergence)
    severity TEXT CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', NULL)),
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, bar_id, signal_type)
);

CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_signal_type ON signals(signal_type);
CREATE INDEX idx_signals_signal_time_utc ON signals(signal_time_utc);


-- ──────────────────────────────────────────────────────────────────────────────
-- Regimes: Market regime tracking
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity
    symbol TEXT NOT NULL,
    regime TEXT NOT NULL CHECK (regime IN ('TREND', 'CHOP', 'BREAKOUT', 'REVERSAL')),
    
    -- Timing
    bar_id INTEGER NOT NULL,
    start_time_utc TEXT NOT NULL,
    session TEXT NOT NULL,
    
    -- End (if regime has changed)
    end_time_utc TEXT,
    duration_bars INTEGER,
    
    -- Quality metrics
    regime_strength INTEGER,  -- 0-100: how confidently detected
    h_c_height INTEGER,  -- Peak histogram value in regime
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, bar_id)
);

CREATE INDEX idx_regimes_symbol ON regimes(symbol);
CREATE INDEX idx_regimes_regime ON regimes(regime);


-- ──────────────────────────────────────────────────────────────────────────────
-- Snapshots: Market snapshot audit trail (optional detailed logging)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity
    symbol TEXT NOT NULL,
    bar_id INTEGER NOT NULL,
    
    -- OHLCV
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    
    -- Indicators
    vwap REAL NOT NULL,
    atr REAL NOT NULL,
    atr_1m REAL NOT NULL,
    cvd_value REAL NOT NULL,
    cvd_zscore REAL NOT NULL,
    
    -- Signal
    h_c_value INTEGER,
    regime TEXT,
    
    -- Timing
    snapshot_time_utc TEXT NOT NULL,
    session TEXT NOT NULL,
    
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, bar_id)
);

CREATE INDEX idx_snapshots_symbol ON snapshots(symbol);
CREATE INDEX idx_snapshots_snapshot_time_utc ON snapshots(snapshot_time_utc);

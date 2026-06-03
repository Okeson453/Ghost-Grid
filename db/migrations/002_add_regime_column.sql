-- Migration 002: Add Regime Column to Positions
-- Enables filtering positions by market regime at entry time

-- Add regime_entry column if it doesn't exist (for rollforward compatibility)
-- Note: In SQLite, we can't add NOT NULL constraints to existing tables easily,
-- so this migration is documented but regime_entry is added in 001_initial_schema.sql

-- This migration file documents the pattern for future schema evolution.
-- For now, all regime columns are created in 001_initial_schema.sql

-- Future migrations would follow pattern:
-- ALTER TABLE positions ADD COLUMN new_column TEXT DEFAULT 'value';
-- CREATE INDEX idx_positions_new_column ON positions(new_column);

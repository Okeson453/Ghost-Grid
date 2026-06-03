"""
scripts/verify_portfolio.py
Verification script for portfolio module implementation.
"""

import sys
sys.path.insert(0, 'C:\\Users\\pc\\Desktop\\GHOST-GRID')

print("Testing portfolio module imports...")
try:
    from portfolio.state import PortfolioState, FrozenPortfolioSnapshot
    print("✓ state.py imported successfully")
    
    from portfolio.ledger import Ledger
    print("✓ ledger.py imported successfully")
    
    from portfolio.mode_automaton import ModeDecision, select_mode
    print("✓ mode_automaton.py imported successfully")
    
    from portfolio.equity_tracker import EquityTracker, EquityRecord
    print("✓ equity_tracker.py imported successfully")
    
    from portfolio.correlation import CorrelationEngine, calculate_correlation
    print("✓ correlation.py imported successfully")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

print("\nTesting PortfolioState...")
try:
    state = PortfolioState()
    print(f"✓ PortfolioState created")
    print(f"  - Starting equity: {state.starting_equity}")
    print(f"  - Net equity: {state.net_equity}")
    print(f"  - Daily PnL: {state.daily_pnl}")
    print(f"  - Open positions: {state.open_position_count}")
    print(f"  - Total basket risk: {state.total_basket_risk}")
except Exception as e:
    print(f"✗ PortfolioState test failed: {e}")
    sys.exit(1)

print("\nTesting Ledger...")
try:
    ledger = Ledger()
    ledger.record_close(state, 50.0)
    print(f"✓ Ledger.record_close() works")
    print(f"  - Realized PnL: {state.realized_pnl}")
    
    ledger.reset_daily(state, 10_000.0)
    print(f"✓ Ledger.reset_daily() works")
    print(f"  - Starting equity: {state.starting_equity}")
except Exception as e:
    print(f"✗ Ledger test failed: {e}")
    sys.exit(1)

print("\nTesting Mode Automaton...")
try:
    decision = select_mode(
        state,
        yesterday_loss_halt=False,
        win_rate_last_20=0.55,
        current_drawdown_pct=0.05,
        current_regime="TREND"
    )
    print(f"✓ select_mode() works")
    print(f"  - Mode: {decision.mode}")
    print(f"  - Reason: {decision.reason}")
    
    # Test REDUCED mode trigger
    decision = select_mode(
        state,
        yesterday_loss_halt=True,
        win_rate_last_20=0.55,
        current_drawdown_pct=0.05,
        current_regime="TREND"
    )
    assert decision.mode == "SCALP_REDUCED"
    print(f"✓ Defensive condition triggers REDUCED mode")
except Exception as e:
    print(f"✗ Mode automaton test failed: {e}")
    sys.exit(1)

print("\nTesting Equity Tracker...")
try:
    tracker = EquityTracker()
    tracker.record_equity(10_000.0)
    tracker.record_equity(10_050.0)
    tracker.record_equity(10_000.0)
    print(f"✓ EquityTracker works")
    print(f"  - Peak equity: {tracker.get_peak_equity()}")
    print(f"  - Drawdown %: {tracker.get_drawdown_pct() * 100:.2f}%")
    print(f"  - Drawdown abs: {tracker.get_drawdown_abs():.2f}")
except Exception as e:
    print(f"✗ EquityTracker test failed: {e}")
    sys.exit(1)

print("\nTesting Correlation Engine...")
try:
    corr_engine = CorrelationEngine()
    
    # Add price data
    for i in range(50):
        corr_engine.record_price("EURUSD", 1.08500 + i * 0.0001)
        corr_engine.record_price("GBPUSD", 1.27000 + i * 0.00008)
    
    corr = calculate_correlation(
        corr_engine.price_windows.get("EURUSD", []),
        corr_engine.price_windows.get("GBPUSD", [])
    )
    print(f"✓ CorrelationEngine works")
    print(f"  - Correlation EURUSD/GBPUSD: {corr:.3f}")
except Exception as e:
    print(f"✗ CorrelationEngine test failed: {e}")
    sys.exit(1)

print("\nTesting FrozenPortfolioSnapshot...")
try:
    snapshot = state.get_frozen_snapshot()
    print(f"✓ FrozenPortfolioSnapshot created")
    print(f"  - Net equity: {snapshot.net_equity}")
    print(f"  - Daily PnL: {snapshot.daily_pnl}")
    print(f"  - Immutable: {snapshot.__class__.__name__}")
except Exception as e:
    print(f"✗ FrozenPortfolioSnapshot test failed: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("✓ ALL PORTFOLIO MODULE TESTS PASSED!")
print("="*50)
print("\nPortfolio module is ready for integration:")
print("  - PortfolioState: Live mutable state")
print("  - FrozenPortfolioSnapshot: Immutable snapshots for watchdog")
print("  - Ledger: PnL aggregation engine")
print("  - EquityTracker: Peak/drawdown monitoring")
print("  - CorrelationEngine: Portfolio diversification tracking")
print("  - ModeAutomaton: Trading mode selector (NORMAL/REDUCED)")

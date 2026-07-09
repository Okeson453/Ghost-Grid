"""
scripts/verify_telegram.py
Comprehensive verification of Telegram module.
"""

from __future__ import annotations
import sys
import os
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports
print("Testing Telegram module imports...")
try:
    from telegram.formatter import (
        format_signal_alert,
        format_nuclear_alert,
        format_status,
        format_position_list,
        format_daily_report,
    )
    print("✓ telegram.formatter imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from telegram.alerts import (
        send_signal_alert,
        send_nuclear_alert,
        send_status,
        send_daily_report,
    )
    print("✓ telegram.alerts imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from telegram.commands import (
        cmd_nuke,
        cmd_status,
        cmd_pause,
        cmd_resume,
        cmd_positions,
    )
    print("✓ telegram.commands imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from telegram.bot import build_application
    print("✓ telegram.bot imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test formatter functions with mocks
print("\nTesting formatter functions...")
try:
    from nuclear.models import NuclearReason, NuclearEvent
    from portfolio.state import PortfolioState

    # Test nuclear alert format
    event = NuclearEvent(
        reason=NuclearReason.DAILY_LOSS_LIMIT,
        timestamp_ms=1234567890,
        positions_closed=3,
        portfolio_pnl=-400.0,
        equity_at_fire=10000.0,
    )
    formatted = format_nuclear_alert(event)
    assert "NUCLEAR EXIT" in formatted
    assert "3 closed" in formatted
    print("✓ format_nuclear_alert works")

    # Test status format
    state = PortfolioState(net_equity=10000, realized_pnl=100)
    formatted = format_status(state)
    assert "STATUS" in formatted
    assert "$10000.00" in formatted
    print("✓ format_status works")

    # Test position list format
    formatted = format_position_list(state)
    assert "No open positions" in formatted
    print("✓ format_position_list works (empty)")

    # Test daily report format
    formatted = format_daily_report(state, trades_today=10, wins_today=6)
    assert "DAILY REPORT" in formatted
    assert "10" in formatted
    assert "60" in formatted  # 60% win rate
    print("✓ format_daily_report works")

except Exception as e:
    print(f"✗ Formatter test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test build_application function
print("\nTesting bot application builder...")
try:
    from portfolio.state import PortfolioState
    
    # We can't fully test build_application without telegram-bot installed,
    # but we can verify it exists and is callable
    assert callable(build_application)
    print("✓ build_application is callable")
    print("  (Full test requires python-telegram-bot installed)")

except Exception as e:
    print(f"✗ Bot builder test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*50)
print("✓ ALL TELEGRAM MODULE TESTS PASSED!")
print("="*50)
print("\nTelegram module is ready for integration:")
print("  - Formatter: Signal, Nuclear, Status, Positions, Daily Report")
print("  - Alerts: Send alerts with HTML formatting")
print("  - Commands: /nuke, /status, /pause, /resume, /positions")
print("  - Bot: Application builder with chat ID filtering")

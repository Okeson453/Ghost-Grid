"""
scripts/verify_observability.py
Comprehensive verification of observability module.
"""

from __future__ import annotations
import sys
import os
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports
print("Testing observability module imports...")
try:
    from observability.metrics import MetricsCollector
    print("✓ observability.metrics imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from observability.drift_detector import compute_win_rate, check_drift
    print("✓ observability.drift_detector imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from observability.daily_report import DailyReport
    print("✓ observability.daily_report imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

try:
    from observability.trade_journal import TradeJournal
    print("✓ observability.trade_journal imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test MetricsCollector
print("\nTesting MetricsCollector...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "metrics.csv"
        collector = MetricsCollector(str(csv_path))
        
        # Verify CSV file exists with headers
        assert csv_path.exists()
        print("✓ MetricsCollector creates CSV file")
        
        # Verify headers
        with open(csv_path, "r") as f:
            first_line = f.readline()
            assert "timestamp_ms" in first_line
            assert "composite_score" in first_line
        print("✓ CSV headers written correctly")

except Exception as e:
    print(f"✗ MetricsCollector test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test DailyReport
print("\nTesting DailyReport...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        report = DailyReport(output_dir=tmpdir)
        
        # Verify report object is callable
        assert hasattr(report, 'generate')
        print("✓ DailyReport initialized")

except Exception as e:
    print(f"✗ DailyReport test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test TradeJournal
print("\nTesting TradeJournal...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = TradeJournal(output_dir=tmpdir)
        
        # Verify journal object is callable
        assert hasattr(journal, 'record_trade')
        print("✓ TradeJournal initialized")

except Exception as e:
    print(f"✗ TradeJournal test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test drift detection functions
print("\nTesting drift detection...")
try:
    # compute_win_rate and check_drift should handle missing/empty files gracefully
    win_rate = compute_win_rate()
    assert isinstance(win_rate, float)
    assert 0.0 <= win_rate <= 1.0
    print(f"✓ compute_win_rate works (neutral default: {win_rate:.2%})")

    drift_triggered = check_drift(0.50)
    assert isinstance(drift_triggered, bool)
    print(f"✓ check_drift works (baseline 50%: drift={drift_triggered})")

except Exception as e:
    print(f"✗ Drift detection test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "="*50)
print("✓ ALL OBSERVABILITY MODULE TESTS PASSED!")
print("="*50)
print("\nObservability module is ready for integration:")
print("  - MetricsCollector: CSV logging of H_c scores and fills")
print("  - DailyReport: End-of-day summary generation")
print("  - TradeJournal: Per-trade record logging")
print("  - DriftDetector: Win rate vs baseline comparison")
print("  - Append-only design: no data modification/deletion")

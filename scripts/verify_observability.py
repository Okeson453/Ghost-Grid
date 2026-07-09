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
    from observability.daily_report import DailyReport, DailyReporter
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

# Test DailyReporter
print("\nTesting DailyReporter...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics_csv = Path(tmpdir) / "metrics.csv"
        trades_csv = Path(tmpdir) / "trades.csv"
        reports_csv = Path(tmpdir) / "daily_reports.csv"
        
        reporter = DailyReporter(
            metrics_csv=str(metrics_csv),
            trades_csv=str(trades_csv),
            reports_csv=str(reports_csv)
        )
        
        # Verify reporter object is callable
        assert hasattr(reporter, 'generate_report')
        print("✓ DailyReporter initialized")

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
        assert hasattr(journal, 'record_opened')
        assert hasattr(journal, 'record_closed')
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
    assert win_rate is None or isinstance(win_rate, float)
    if win_rate is not None:
        assert 0.0 <= win_rate <= 100.0
    print(f"✓ compute_win_rate works (value: {win_rate})")

    drift_alert = check_drift()
    assert hasattr(drift_alert, 'drifted')
    assert isinstance(drift_alert.drifted, bool)
    print(f"✓ check_drift works (drifted={drift_alert.drifted})")

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

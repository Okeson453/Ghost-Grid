"""
data_store/__init__.py
Data store initialization and management.

Provides utilities for artifact curation, trace export, and dataset management.
"""

from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Root data store path
DATA_STORE_ROOT = Path(__file__).parent

# Subdirectories
DATASETS_DIR = DATA_STORE_ROOT / "datasets"
TRACES_DIR = DATA_STORE_ROOT / "traces"
SIGNALS_DIR = DATA_STORE_ROOT / "signals"
PERFORMANCE_DIR = DATA_STORE_ROOT / "performance"


def init_data_store() -> None:
    """Initialize data store directories on startup."""
    for d in [DATASETS_DIR, TRACES_DIR, SIGNALS_DIR, PERFORMANCE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Data store directory ready: {d.name}")


def get_trace_path(date: datetime, symbol: str = None) -> Path:
    """
    Get path for trace file.

    Args:
        date: datetime object (will extract YYYY/MM/DD)
        symbol: optional symbol filter (e.g., "EURUSD")

    Returns:
        Path object for trace directory or file
    """
    trace_dir = TRACES_DIR / date.strftime("%Y/%m/%d")
    trace_dir.mkdir(parents=True, exist_ok=True)

    if symbol:
        return trace_dir / f"{symbol}.jsonl"
    return trace_dir


def get_signal_path(date: datetime, symbol: str = None) -> Path:
    """
    Get path for signal file.

    Args:
        date: datetime object (will extract YYYY/MM)
        symbol: optional symbol filter

    Returns:
        Path object for signal directory or file
    """
    signal_dir = SIGNALS_DIR / date.strftime("%Y/%m")
    signal_dir.mkdir(parents=True, exist_ok=True)

    if symbol:
        return signal_dir / f"{date.strftime('%d')}_{symbol}_signals.csv"
    return signal_dir


def get_performance_path(path_type: str, date: datetime = None) -> Path:
    """
    Get path for performance report.

    Args:
        path_type: "daily" | "monthly" | "regime_analysis"
        date: optional date for daily/monthly reports

    Returns:
        Path object for performance file
    """
    if path_type == "daily":
        perf_dir = PERFORMANCE_DIR / "daily"
        perf_dir.mkdir(parents=True, exist_ok=True)
        filename = date.strftime("%Y_%m_%d.json") if date else None
        return perf_dir / filename if filename else perf_dir

    elif path_type == "monthly":
        perf_dir = PERFORMANCE_DIR / "monthly"
        perf_dir.mkdir(parents=True, exist_ok=True)
        filename = date.strftime("%Y_%m_summary.json") if date else None
        return perf_dir / filename if filename else perf_dir

    else:  # regime_analysis
        perf_dir = PERFORMANCE_DIR / "regime_analysis"
        perf_dir.mkdir(parents=True, exist_ok=True)
        return perf_dir


def get_dataset_path(version: str = "v1.0") -> Path:
    """
    Get path for ML dataset versioned directory.

    Args:
        version: dataset version (e.g., "v1.0", "v1.1")

    Returns:
        Path object for dataset directory
    """
    dataset_dir = DATASETS_DIR / version
    dataset_dir.mkdir(parents=True, exist_ok=True)
    return dataset_dir


__all__ = [
    "init_data_store",
    "get_trace_path",
    "get_signal_path",
    "get_performance_path",
    "get_dataset_path",
    "DATA_STORE_ROOT",
    "DATASETS_DIR",
    "TRACES_DIR",
    "SIGNALS_DIR",
    "PERFORMANCE_DIR",
]

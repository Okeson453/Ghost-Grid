"""
bridge/__init__.py
Public API for bridge package.

Import from here, never from submodules.
Exports all communication, metrics, and management classes for enterprise monitoring.
"""

from .pipe_client import PipeClient, PipeClientMetrics
from .reader import PipeReader, ReaderMetrics
from .writer import PipeWriter, WriterMetrics
from .protocol import parse_inbound, ParseMetrics, get_parse_metrics
from .reconnect import ReconnectManager, ReconnectMetrics
from .health import PipeHealthMonitor

__all__ = [
    # Clients and managers
    "PipeClient",
    "PipeReader",
    "PipeWriter",
    "ReconnectManager",
    "PipeHealthMonitor",
    # Metrics
    "PipeClientMetrics",
    "ReaderMetrics",
    "WriterMetrics",
    "ParseMetrics",
    "ReconnectMetrics",
    # Utilities
    "parse_inbound",
    "get_parse_metrics",
]

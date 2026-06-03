"""
db package public API.
Import from here — never from sub-modules directly.
"""

from .connection import ConnectionPool, get_pool, ConnectionMetrics
from .writer import DatabaseWriter, WriterMetrics
from .reader import DatabaseReader, ReaderMetrics
from .recovery import DatabaseRecovery, RecoveryMetrics

__all__ = [
    "ConnectionPool",
    "get_pool",
    "ConnectionMetrics",
    "DatabaseWriter",
    "WriterMetrics",
    "DatabaseReader",
    "ReaderMetrics",
    "DatabaseRecovery",
    "RecoveryMetrics",
]

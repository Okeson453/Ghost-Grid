"""
security/
Security modules for GHOST-GRID.

Modules:
  - sanitization:    Input validation and sanitization for pipe protocol
  - rate_limiter:    Per-user rate limiting for Telegram commands
  - audit_log:       Audit trail for manual commands
"""

from security.sanitization import (
    sanitize_symbol,
    sanitize_position_id,
    sanitize_direction,
    sanitize_price,
    sanitize_volume,
    sanitize_lots,
    get_sanitization_metrics,
)

from security.rate_limiter import (
    check_rate_limit,
    RateLimitAction,
    get_rate_limiter_metrics,
)

from security.audit_log import (
    AuditAction,
    log_action,
    get_audit_log,
    init_audit_table,
)

__all__ = [
    "sanitize_symbol",
    "sanitize_position_id",
    "sanitize_direction",
    "sanitize_price",
    "sanitize_volume",
    "sanitize_lots",
    "get_sanitization_metrics",
    "check_rate_limit",
    "RateLimitAction",
    "get_rate_limiter_metrics",
    "AuditAction",
    "log_action",
    "get_audit_log",
    "init_audit_table",
]

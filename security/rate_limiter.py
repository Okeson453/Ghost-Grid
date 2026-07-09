"""
security/rate_limiter.py
Per-user rate limiting for Telegram commands.

Prevents command spam and DoS attacks by tracking command frequency per user.
Uses simple in-memory token bucket with time-window decay.
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from typing import Dict
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitAction(str, Enum):
    """Actions subject to rate limiting."""

    NUKE = "NUKE"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STATUS = "STATUS"
    POSITIONS = "POSITIONS"


# Rate limit windows (commands per minute, resets per window)
RATE_LIMITS: Dict[RateLimitAction, int] = {
    RateLimitAction.NUKE: 3,  # Max 3 nukes per minute
    RateLimitAction.PAUSE: 10,  # Max 10 pauses per minute
    RateLimitAction.RESUME: 10,  # Max 10 resumes per minute
    RateLimitAction.STATUS: 30,  # Max 30 status checks per minute
    RateLimitAction.POSITIONS: 30,  # Max 30 position checks per minute
}

WINDOW_SIZE_SEC = 60  # 60-second rolling window


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    user_id: int
    action: RateLimitAction
    tokens: int = 0
    last_update_ts: float = field(default_factory=time.time)

    def refill(self, now: float) -> None:
        """Refill tokens based on elapsed time."""
        elapsed = now - self.last_update_ts
        max_tokens = RATE_LIMITS[self.action]
        # Add tokens at rate of 1 token per second, capped at max
        self.tokens = min(
            max_tokens,
            self.tokens + elapsed * (max_tokens / WINDOW_SIZE_SEC),
        )
        self.last_update_ts = now

    def try_consume(self, now: float, cost: int = 1) -> bool:
        """
        Try to consume tokens.
        Returns True if allowed, False if rate limited.
        """
        self.refill(now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class RateLimiter:
    """Global rate limiter for all users."""

    def __init__(self):
        self._buckets: Dict[tuple[int, RateLimitAction], TokenBucket] = {}
        self._cleanup_interval = 300  # Clean up old buckets every 5 min
        self._last_cleanup = time.time()

    def check_limit(
        self,
        user_id: int,
        action: RateLimitAction,
    ) -> bool:
        """
        Check if user can perform action.
        Returns True if allowed, False if rate limited.

        Always allows (returns True) unless explicitly rate limited.
        """
        now = time.time()

        # Periodic cleanup of old buckets
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_buckets(now)

        key = (user_id, action)
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(user_id, action)

        bucket = self._buckets[key]
        allowed = bucket.try_consume(now)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded: user={user_id}, action={action.value}, "
                f"tokens={bucket.tokens:.2f}"
            )

        return allowed

    def _cleanup_old_buckets(self, now: float) -> None:
        """Remove buckets not accessed in the past hour."""
        cutoff = now - 3600  # 1 hour
        expired_keys = [
            key
            for key, bucket in self._buckets.items()
            if bucket.last_update_ts < cutoff
        ]
        for key in expired_keys:
            del self._buckets[key]
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit buckets")

    def get_metrics(self) -> dict:
        """Return rate limiter metrics."""
        now = time.time()
        return {
            "total_buckets": len(self._buckets),
            "actions": {
                action.value: len(
                    [k for k in self._buckets.keys() if k[1] == action]
                )
                for action in RateLimitAction
            },
        }


# Global rate limiter singleton
_limiter = RateLimiter()


def check_rate_limit(user_id: int, action: RateLimitAction) -> bool:
    """
    Check if user can perform action (thread-safe).

    Args:
        user_id: Telegram user ID
        action:  RateLimitAction enum

    Returns:
        True if allowed, False if rate limited.
    """
    return _limiter.check_limit(user_id, action)


def get_rate_limiter_metrics() -> dict:
    """Get rate limiter metrics."""
    return _limiter.get_metrics()

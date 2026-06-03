"""
Nuclear Portfolio Guardian — emergency circuit breaker system.

Monitors portfolio state every 500ms and fires all positions simultaneously
when any of 7 trigger conditions are met. Enforces cooldown and daily halt
logic after nuclear event.
"""

from __future__ import annotations

from nuclear.models import NuclearReason, NuclearEvent
from nuclear.triggers import evaluate_triggers, TRIGGERS
from nuclear.executor import execute_nuclear_close
from nuclear.cooldown import apply_cooldown, NuclearCooldown
from nuclear.controller import NuclearController

__all__ = [
    "NuclearReason",
    "NuclearEvent",
    "evaluate_triggers",
    "TRIGGERS",
    "execute_nuclear_close",
    "apply_cooldown",
    "NuclearCooldown",
    "NuclearController",
]

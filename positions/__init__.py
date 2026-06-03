"""
positions/__init__.py
Position lifecycle management, state machines, exit engines, and registry.
"""

from .models import PositionState, ExitReason
from .trail_manager import TrailManager, compute_trail_distance
from .weakness import detect_weakness, WeaknessSignal
from .cvd_exit import check_cvd_exit
from .exit_engine import ExitEngine, ExitEvaluation
from .state_machine import PositionStateMachine
from .registry import PositionRegistry

__all__ = [
    "PositionState",
    "ExitReason",
    "TrailManager",
    "compute_trail_distance",
    "detect_weakness",
    "WeaknessSignal",
    "check_cvd_exit",
    "ExitEngine",
    "ExitEvaluation",
    "PositionStateMachine",
    "PositionRegistry",
]

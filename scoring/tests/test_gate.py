"""
Tests for Schmitt hysteresis gate — verify decision logic and cycle counting.
"""

import pytest
from scoring.gate import ConfluenceGate
from scoring.models import GateDecision, ConfluenceScore


def _make_score(
    composite: int,
    symbol: str = "EURUSD",
    regime: str = "TREND",
) -> ConfluenceScore:
    return ConfluenceScore(
        symbol=symbol,
        hmp=composite // 3,
        hlcp=composite // 3,
        mpp=composite - 2 * (composite // 3),
        composite=composite,
        direction="LONG",
        regime=regime,
        session="LONDON",
        timestamp_ms=1_700_000_000_000,
    )


class TestConfluenceGate:
    def test_single_cycle_above_threshold_is_alert(self):
        gate = ConfluenceGate()
        score = _make_score(132)  # TREND threshold=130, one cycle above
        result = gate.evaluate(score)
        assert result == GateDecision.ALERT

    def test_two_cycles_fires_full_auto(self):
        gate = ConfluenceGate()
        gate.evaluate(_make_score(132))  # cycle 1 → ALERT
        result = gate.evaluate(_make_score(132))  # cycle 2 → FULL_AUTO
        assert result == GateDecision.FULL_AUTO

    def test_strong_bonus_fires_full_auto_strong(self):
        gate = ConfluenceGate()
        gate.evaluate(_make_score(152))  # cycle 1 (TREND threshold=130, +20 bonus=150)
        result = gate.evaluate(_make_score(152))
        assert result == GateDecision.FULL_AUTO_STRONG

    def test_drop_below_threshold_resets_counter(self):
        gate = ConfluenceGate()
        gate.evaluate(_make_score(132))  # cycle 1
        gate.evaluate(_make_score(100))  # dropped below → reset
        result = gate.evaluate(_make_score(132))  # cycle 1 again → ALERT
        assert result == GateDecision.ALERT

    def test_watchlist_near_threshold(self):
        gate = ConfluenceGate()
        result = gate.evaluate(
            _make_score(115)
        )  # 130 - 20 = 110, score 115 → watchlist
        assert result == GateDecision.WATCHLIST

    def test_below_watchlist_is_discard(self):
        gate = ConfluenceGate()
        result = gate.evaluate(_make_score(50))
        assert result == GateDecision.DISCARD

    def test_chop_regime_higher_threshold(self):
        """CHOP threshold = 155. Score 132 should be WATCHLIST, not ALERT."""
        gate = ConfluenceGate()
        result = gate.evaluate(_make_score(132, regime="CHOP"))
        # 155 - 20 = 135 → 132 is below watchlist zone
        assert result == GateDecision.DISCARD

    def test_reset_clears_all_state(self):
        gate = ConfluenceGate()
        gate.evaluate(_make_score(132))  # cycle 1
        gate.reset("EURUSD")
        result = gate.evaluate(_make_score(132))  # should restart at cycle 1 → ALERT
        assert result == GateDecision.ALERT

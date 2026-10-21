"""Acceptance test for the demo seed's two-act story (planning #3, eng-review D9).

Expected to fail until second_look.sim exists. The xfail is strict: once the simulator
lands and this passes, remove the marker.
"""

import pytest

pytestmark = pytest.mark.xfail(
    raises=(ImportError, AttributeError), strict=True, reason="simulator lands in planning #3"
)


def _demo():
    from second_look.sim import simulate_seed

    return simulate_seed("demo")


def test_first_half_volume_without_quality():
    shots = [e for e in _demo() if e.type == "shot" and e.team == "nel" and e.period == 1]
    assert len(shots) >= 9
    assert sum(e.xg for e in shots) / len(shots) < 0.07


def test_after_half_time_nel_create_real_chances():
    events = _demo()
    xg = sum(e.xg for e in events if e.type == "shot" and e.team == "nel" and 46 <= e.minute <= 60)
    assert xg >= 1.2


def test_yob_lead_flatters_them_at_60():
    events = [e for e in _demo() if e.minute <= 60]
    yob_xg = sum(e.xg for e in events if e.type == "shot" and e.team == "yob")
    yob_goals = sum(1 for e in events if e.type == "goal" and e.team == "yob")
    assert yob_goals == 2
    assert yob_xg <= 0.5


def test_score_is_0_2_at_60_and_1_2_at_78():
    goals = [e for e in _demo() if e.type == "goal"]

    def score(by):
        return (sum(1 for g in goals if g.team == "nel" and g.minute <= by),
                sum(1 for g in goals if g.team == "yob" and g.minute <= by))

    assert score(60) == (0, 2)
    assert score(78) == (1, 2)

"""Prediction lifecycle: one open per team, fulfil on goal, expire on deadline or full time."""

import pytest

from second_look.ledger import Ledger


def test_one_open_prediction_per_team():
    ledger = Ledger()
    ledger.make("nel", 60, "A goal is coming.")
    with pytest.raises(ValueError):
        ledger.make("nel", 65, "Again.")
    ledger.make("yob", 65, "Other team is fine.")


def test_goal_before_deadline_fulfils_and_frees_the_team():
    ledger = Ledger()
    ledger.make("nel", 60, "x")
    assert ledger.goal("yob", 70) is None  # wrong team
    fulfilled = ledger.goal("nel", 85)  # deadline minute itself counts
    assert (fulfilled.id, fulfilled.status) == ("pr_nel_60", "fulfilled")
    assert not ledger.has_open("nel")


def test_deadline_passes_then_expires():
    ledger = Ledger()
    ledger.make("nel", 50, "x")  # by 75
    assert ledger.expire(75) == []
    assert ledger.goal("nel", 76) is None  # too late
    assert [p.status for p in ledger.expire(80)] == ["expired"]


def test_full_time_expires_everything_open():
    ledger = Ledger()
    ledger.make("nel", 80, "x")  # by 90
    assert [(p.id, p.by_minute, p.status) for p in ledger.expire(90, full_time=True)] == [("pr_nel_80", 90, "expired")]
    assert ledger.open == {}

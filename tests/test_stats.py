"""The per-team stats the newer detectors read: possession time, box entries and pressing by game state."""

from second_look.contracts import Event
from second_look.stats import match_state


def _ev(i, t, type_, team, **kw):
    return Event(id=i, t=t, minute=int(t // 60), period=1, type=type_, team=team, **kw)


EVENTS = [
    _ev(0, 0, "possession_start", "nel", sequence_id=1),
    _ev(1, 10, "pass", "nel", sequence_id=1, x=80, y=34, end_x=95, end_y=34, outcome="complete"),  # box entry
    _ev(2, 20, "pass", "nel", sequence_id=1, x=95, y=34, end_x=96, end_y=60, outcome="complete"),  # wide of box
    _ev(3, 30, "pressure", "nel", x=60, y=30),  # level
    _ev(4, 40, "carry", "nel", sequence_id=1, x=70, y=30, end_x=90, end_y=30, outcome="incomplete"),  # not complete
    _ev(5, 60, "possession_end", "nel", sequence_id=1),
    _ev(6, 60, "possession_start", "yob", sequence_id=2),
    _ev(7, 90, "possession_end", "yob", sequence_id=2),
    _ev(8, 120, "goal", "yob"),
    _ev(9, 200, "pressure", "nel", x=60, y=30),  # behind
]


def test_possession_box_entries_and_pressing_split_by_score():
    state = match_state(EVENTS, "nel", "yob", minute=5, window_minutes=30)
    nel = state.home
    assert (nel.possession_s, state.away.possession_s) == (60, 30)
    assert round(state.possession_share("nel"), 2) == 0.67
    assert nel.box_entries == 1  # only the completed pass that ends inside the box
    # Minutes sampled at each start: 0', 1', 2' level (the goal lands at 2:00 exactly), 3' behind.
    assert (nel.pressures_level, nel.minutes_level, nel.pressures_behind, nel.minutes_behind) == (1, 3, 1, 1)
    assert state.away.minutes_behind == 0

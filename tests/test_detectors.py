"""Detector thresholds, dedup and the per-window pick."""

from second_look.detectors import Picker, effort_game_state, possession_penetration, scoreline_xg, volume_quality
from second_look.stats import MatchState, TeamStats


def _team(team, shots=0, xg=0.0, goals=0, xg_window=0.0, **more):
    return TeamStats(team=team, shots=shots, xg=xg, avg_shot_distance_m=25.0, goals=goals, xg_window=xg_window, **more)


def _state(home, away, minute=35):
    return MatchState(minute=minute, home=home, away=away, window_from_minute=max(0, minute - 30))


def test_volume_quality_fires_on_many_poor_shots():
    found = volume_quality(_state(_team("nel", shots=8, xg=0.4), _team("yob", shots=2, xg=0.3)))
    assert [(c.team, c.detector) for c in found] == [("nel", "volume_quality")]
    assert 0 < found[0].severity <= 1


def test_volume_quality_silent_below_eight_shots_or_at_the_quality_threshold():
    assert volume_quality(_state(_team("nel", shots=7, xg=0.1), _team("yob"))) == []
    assert volume_quality(_state(_team("nel", shots=10, xg=0.8), _team("yob"))) == []  # 0.08 per shot


def test_scoreline_xg_fires_for_the_trailing_team_ahead_on_window_xg():
    found = scoreline_xg(_state(_team("nel", goals=0, xg_window=1.3), _team("yob", goals=2, xg_window=0.1), 60))
    assert [(c.team, c.evidence["leader"], c.window_from_minute) for c in found] == [("nel", "yob", 30)]


def test_scoreline_xg_silent_when_level_or_gap_too_small():
    assert scoreline_xg(_state(_team("nel", goals=1, xg_window=2.0), _team("yob", goals=1))) == []
    assert scoreline_xg(_state(_team("nel", goals=0, xg_window=1.0), _team("yob", goals=1, xg_window=0.1))) == []


def _vq(minute, xg):
    return volume_quality(_state(_team("nel", shots=10, xg=xg), _team("yob"), minute))


def test_dedup_holds_a_repeat_until_15_minutes_or_a_quarter_more_severity():
    picker = Picker()
    assert picker.pick(_vq(35, 0.6), set()) is not None  # severity 0.25
    assert picker.pick(_vq(40, 0.6), set()) is None  # same severity, 5 minutes later
    assert picker.pick(_vq(45, 0.2), set()) is not None  # severity 0.75: rise >= 0.25
    assert picker.pick(_vq(55, 0.2), set()) is None
    assert picker.pick(_vq(60, 0.2), set()) is not None  # 15 minutes later


def test_a_new_prediction_wins_the_window_and_skips_dedup():
    picker = Picker()
    vq = _vq(60, 0.1)[0]  # severity ~0.88
    sx = scoreline_xg(_state(_team("nel", goals=0, xg_window=1.2), _team("yob", goals=1), 60))[0]  # ~0.2
    assert picker.pick([vq, sx], set()) is vq
    assert picker.pick([vq, sx], {sx.id}) is sx


def test_possession_penetration_fires_on_lots_of_ball_and_few_box_entries():
    # nel: 70% of the ball, 1 entry per 10 possession-min; yob: 3 per 10. 1/3 < 0.6.
    nel, yob = _team("nel", possession_s=2100, box_entries=7), _team("yob", possession_s=900, box_entries=9)
    found = possession_penetration(_state(nel, yob))
    assert [(c.team, c.evidence["possession_pct"], c.evidence["opponent"]) for c in found] == [("nel", 70, "yob")]
    assert 0 < found[0].severity <= 1


def test_possession_penetration_silent_under_sixty_percent_or_when_entries_keep_up():
    yob = _team("yob", possession_s=1000, box_entries=10)
    assert possession_penetration(_state(_team("nel", possession_s=1400, box_entries=1), yob)) == []  # 58%
    assert possession_penetration(_state(_team("nel", possession_s=2100, box_entries=15), yob)) == []  # 0.71 ratio


def test_effort_game_state_fires_when_a_trailing_team_stops_pressing():
    # nel behind 20 min at 2 per 5 min, after 20 min level at 6 per 5 min. 2/6 < 0.7.
    nel = _team("nel", pressures_behind=8, minutes_behind=20, pressures_level=24, minutes_level=20)
    found = effort_game_state(_state(nel, _team("yob", goals=1), 40))
    assert [(c.team, c.evidence["press_rate_while_behind"], c.evidence["press_rate_while_level"]) for c in found] == [
        ("nel", 2.0, 6.0)
    ]


def test_effort_game_state_silent_when_level_too_briefly_behind_or_still_pressing():
    yob = _team("yob", goals=1)
    still = _team("nel", pressures_behind=20, minutes_behind=20, pressures_level=24, minutes_level=20)
    brief = _team("nel", pressures_behind=0, minutes_behind=5, pressures_level=24, minutes_level=20)
    assert effort_game_state(_state(still, yob, 40)) == []  # 5 vs 6 per 5 min
    assert effort_game_state(_state(brief, yob, 40)) == []  # under 10 minutes behind
    assert effort_game_state(_state(_team("nel", pressures_level=24, minutes_level=20), _team("yob"))) == []  # level

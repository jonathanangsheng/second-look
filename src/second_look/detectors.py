"""Detectors that find a misleading headline stat, plus the dedup and per-window pick."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from second_look import config
from second_look.contracts import Contradiction, StatValue
from second_look.stats import MatchState


def volume_quality(state: MatchState) -> list[Contradiction]:
    """Many shots, little quality: shots >= VQ_MIN_SHOTS and xG/shot < VQ_MAX_XG_PER_SHOT."""
    found = []
    for t in (state.home, state.away):
        if t.shots >= config.VQ_MIN_SHOTS and t.xg_per_shot < config.VQ_MAX_XG_PER_SHOT:
            limit = config.VQ_MAX_XG_PER_SHOT
            found.append(
                Contradiction(
                    id=f"c_{t.team}_volume_quality_{state.minute}",
                    detector="volume_quality",
                    team=t.team,
                    minute=state.minute,
                    surface=StatValue(label="shots", value=t.shots),
                    truth=StatValue(label="xG per shot", value=round(t.xg_per_shot, 3)),
                    evidence={
                        "team": t.team,
                        "minute": state.minute,
                        "shots": t.shots,
                        "xg_total": round(t.xg, 2),
                        "xg_per_shot": round(t.xg_per_shot, 3),
                        "threshold": limit,
                        "avg_shot_distance_m": round(t.avg_shot_distance_m),
                        "score_home": state.home.goals,
                        "score_away": state.away.goals,
                    },
                    evidence_display={},
                    severity=round(min(1.0, (limit - t.xg_per_shot) / limit), 3),
                )
            )
    return found


def scoreline_xg(state: MatchState) -> list[Contradiction]:
    """The scoreline lies: over the rolling window, the trailing team's xG beats the leader's by SX_XG_GAP."""
    if state.home.goals == state.away.goals:
        return []
    leader, trailer = (state.home, state.away) if state.home.goals > state.away.goals else (state.away, state.home)
    gap = trailer.xg_window - leader.xg_window
    if gap < config.SX_XG_GAP:
        return []
    return [
        Contradiction(
            id=f"c_{trailer.team}_scoreline_xg_{state.minute}",
            detector="scoreline_xg",
            team=trailer.team,
            minute=state.minute,
            surface=StatValue(label="goal difference", value=trailer.goals - leader.goals),
            truth=StatValue(label="xG difference since window start", value=round(gap, 2)),
            evidence={
                "trailer": trailer.team,
                "leader": leader.team,
                "minute": state.minute,
                "window_from_minute": state.window_from_minute,
                "trailer_xg_window": round(trailer.xg_window, 1),
                "leader_xg_window": round(leader.xg_window, 1),
                "threshold": config.SX_XG_GAP,
                "score_home": state.home.goals,
                "score_away": state.away.goals,
            },
            evidence_display={},
            severity=round(min(1.0, (gap - config.SX_XG_GAP) / config.SX_XG_GAP), 3),
            window_from_minute=state.window_from_minute,
        )
    ]


def possession_penetration(state: MatchState) -> list[Contradiction]:
    """The ball, not the box: possession >= PP_MIN_POSSESSION, but box entries per possession-minute
    under PP_MAX_ENTRY_RATIO times the opponent's."""
    if state.minute < config.PP_MIN_MINUTES:
        return []
    found = []
    for t in (state.home, state.away):
        opp, share = state.other(t.team), state.possession_share(t.team)
        if share < config.PP_MIN_POSSESSION or not opp.box_entries_per_10:
            continue
        ratio = t.box_entries_per_10 / opp.box_entries_per_10
        if ratio >= config.PP_MAX_ENTRY_RATIO:
            continue
        found.append(
            Contradiction(
                id=f"c_{t.team}_possession_penetration_{state.minute}",
                detector="possession_penetration",
                team=t.team,
                minute=state.minute,
                surface=StatValue(label="possession %", value=round(share * 100)),
                truth=StatValue(label="box entries per 10 possession minutes", value=round(t.box_entries_per_10, 1)),
                evidence={
                    "team": t.team,
                    "opponent": opp.team,
                    "minute": state.minute,
                    "possession_pct": round(share * 100),
                    "box_entry_rate": round(t.box_entries_per_10, 1),
                    "opponent_box_entry_rate": round(opp.box_entries_per_10, 1),
                    "ratio": round(ratio, 2),
                    "max_ratio": config.PP_MAX_ENTRY_RATIO,
                    "score_home": state.home.goals,
                    "score_away": state.away.goals,
                },
                evidence_display={},
                severity=round((config.PP_MAX_ENTRY_RATIO - ratio) / config.PP_MAX_ENTRY_RATIO, 3),
            )
        )
    return found


def effort_game_state(state: MatchState) -> list[Contradiction]:
    """Effort fades with the scoreline: a team that is behind presses under EG_MAX_PRESS_RATIO times its own
    rate while level or ahead, with at least EG_MIN_MINUTES of each to compare."""
    found = []
    for t in (state.home, state.away):
        if t.goals >= state.other(t.team).goals:
            continue
        if min(t.minutes_behind, t.minutes_level) < config.EG_MIN_MINUTES or not t.press_rate_level:
            continue
        ratio = t.press_rate_behind / t.press_rate_level
        if ratio >= config.EG_MAX_PRESS_RATIO:
            continue
        found.append(
            Contradiction(
                id=f"c_{t.team}_effort_game_state_{state.minute}",
                detector="effort_game_state",
                team=t.team,
                minute=state.minute,
                surface=StatValue(label="goal difference", value=t.goals - state.other(t.team).goals),
                truth=StatValue(label="pressures per 5 min while behind", value=round(t.press_rate_behind, 1)),
                evidence={
                    "team": t.team,
                    "minute": state.minute,
                    "press_rate_while_behind": round(t.press_rate_behind, 1),
                    "press_rate_while_level": round(t.press_rate_level, 1),
                    "minutes_spent_behind": t.minutes_behind,
                    "ratio": round(ratio, 2),
                    "max_ratio": config.EG_MAX_PRESS_RATIO,
                    "score_home": state.home.goals,
                    "score_away": state.away.goals,
                },
                evidence_display={},
                severity=round((config.EG_MAX_PRESS_RATIO - ratio) / config.EG_MAX_PRESS_RATIO, 3),
            )
        )
    return found


DETECTORS: tuple[Callable[[MatchState], list[Contradiction]], ...] = (
    volume_quality,
    scoreline_xg,
    possession_penetration,
    effort_game_state,
)


# Head start in the per-window pick: the original detectors win close calls against the later ones.
PRIORITY = {"volume_quality": config.DEDUP_SEVERITY_RISE, "scoreline_xg": config.DEDUP_SEVERITY_RISE}


def run_all(state: MatchState) -> list[Contradiction]:
    return [c for detect in DETECTORS for c in detect(state)]


@dataclass
class Picker:
    """At most one debate per window, with dedup per (team, detector)."""

    last: dict[tuple[str, str], tuple[int, float]] = field(default_factory=dict)  # -> (minute, severity)

    def pick(self, found: list[Contradiction], predicts: set[str]) -> Contradiction | None:
        """`predicts`: ids of contradictions that would open a new prediction. They win and skip dedup."""
        fresh = [c for c in found if c.id in predicts or self._is_new(c)]
        if not fresh:
            return None
        chosen = max(fresh, key=lambda c: (c.id in predicts, c.severity + PRIORITY.get(c.detector, 0.0)))
        self.last[(chosen.team, chosen.detector)] = (chosen.minute, chosen.severity)
        return chosen

    def _is_new(self, c: Contradiction) -> bool:
        seen = self.last.get((c.team, c.detector))
        if seen is None:
            return True
        minute, severity = seen
        return c.severity >= severity + config.DEDUP_SEVERITY_RISE or c.minute - minute >= config.DEDUP_MINUTES

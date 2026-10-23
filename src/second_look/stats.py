"""Per-team aggregates at a window boundary, from all events before it."""

from __future__ import annotations

import math
from dataclasses import dataclass

from second_look.contracts import PITCH_WIDTH_M, Event
from second_look.sim import GOAL_X, in_box


@dataclass(frozen=True)
class TeamStats:
    team: str
    shots: int
    xg: float
    avg_shot_distance_m: float
    goals: int
    xg_window: float  # xG inside the rolling window ending at the boundary
    possession_s: float = 0.0  # seconds in completed possession sequences
    box_entries: int = 0  # completed passes and carries ending in the opponent's box
    pressures_behind: int = 0  # pressures made while losing, and the minutes spent losing
    minutes_behind: int = 0
    pressures_level: int = 0  # the same while level or ahead
    minutes_level: int = 0

    @property
    def xg_per_shot(self) -> float:
        return self.xg / self.shots if self.shots else 0.0

    @property
    def box_entries_per_10(self) -> float:
        """Box entries per 10 minutes of possession."""
        return self.box_entries / (self.possession_s / 600) if self.possession_s else 0.0

    @property
    def press_rate_behind(self) -> float:
        """Pressures per 5 minutes while losing."""
        return self.pressures_behind / self.minutes_behind * 5 if self.minutes_behind else 0.0

    @property
    def press_rate_level(self) -> float:
        """Pressures per 5 minutes while level or ahead."""
        return self.pressures_level / self.minutes_level * 5 if self.minutes_level else 0.0


@dataclass(frozen=True)
class MatchState:
    minute: int  # the boundary: covers events with minute < this
    home: TeamStats
    away: TeamStats
    window_from_minute: int

    def team(self, team_id: str) -> TeamStats:
        return self.home if team_id == self.home.team else self.away

    def other(self, team_id: str) -> TeamStats:
        return self.away if team_id == self.home.team else self.home

    def possession_share(self, team_id: str) -> float:
        total = self.home.possession_s + self.away.possession_s
        return self.team(team_id).possession_s / total if total else 0.0


def match_state(events: list[Event], home: str, away: str, minute: int, window_minutes: int) -> MatchState:
    before = [e for e in events if e.minute < minute]
    window_from = max(0, minute - window_minutes)
    return MatchState(
        minute=minute,
        home=_team_stats(before, home, window_from),
        away=_team_stats(before, away, window_from),
        window_from_minute=window_from,
    )


def _team_stats(events: list[Event], team: str, window_from: int) -> TeamStats:
    shots = [e for e in events if e.type == "shot" and e.team == team]
    distances = [math.hypot(GOAL_X - e.x, PITCH_WIDTH_M / 2 - e.y) for e in shots]
    goals = [(e.t, e.team == team) for e in events if e.type == "goal"]

    def behind(t: float) -> bool:
        return sum(1 for gt, ours in goals if gt < t and ours) < sum(1 for gt, ours in goals if gt < t and not ours)

    starts, possession_s = {}, 0.0
    for e in events:
        if e.type == "possession_start" and e.team == team:
            starts[e.sequence_id] = e.t
        elif e.type == "possession_end" and e.sequence_id in starts:
            possession_s += e.t - starts.pop(e.sequence_id)
    # One flag per pressure and per match minute: was the team losing at that moment?
    pressed_behind = [behind(e.t) for e in events if e.type == "pressure" and e.team == team]
    minute_behind = [behind(m * 60.0) for m in range(max((e.minute for e in events), default=-1) + 1)]
    return TeamStats(
        team=team,
        shots=len(shots),
        xg=sum(e.xg for e in shots),
        avg_shot_distance_m=sum(distances) / len(distances) if distances else 0.0,
        goals=sum(1 for e in events if e.type == "goal" and e.team == team),
        xg_window=sum(e.xg for e in shots if e.minute >= window_from),
        possession_s=possession_s,
        box_entries=sum(
            1
            for e in events
            if e.team == team and e.type in ("pass", "carry") and e.outcome == "complete" and in_box(e.end_x, e.end_y)
        ),
        pressures_behind=sum(pressed_behind),
        minutes_behind=sum(minute_behind),
        pressures_level=len(pressed_behind) - sum(pressed_behind),
        minutes_level=len(minute_behind) - sum(minute_behind),
    )

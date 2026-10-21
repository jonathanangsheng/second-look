"""Per-team aggregates at a window boundary, from all events before it."""

from __future__ import annotations

import math
from dataclasses import dataclass

from second_look.contracts import PITCH_WIDTH_M, Event
from second_look.sim import GOAL_X


@dataclass(frozen=True)
class TeamStats:
    team: str
    shots: int
    xg: float
    avg_shot_distance_m: float
    goals: int
    xg_window: float  # xG inside the rolling window ending at the boundary

    @property
    def xg_per_shot(self) -> float:
        return self.xg / self.shots if self.shots else 0.0


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
    return TeamStats(
        team=team,
        shots=len(shots),
        xg=sum(e.xg for e in shots),
        avg_shot_distance_m=sum(distances) / len(distances) if distances else 0.0,
        goals=sum(1 for e in events if e.type == "goal" and e.team == team),
        xg_window=sum(e.xg for e in shots if e.minute >= window_from),
    )

"""Seeded synthetic match simulator: team profiles in, Event list out.

A possession-sequence loop: each sequence is a chain of passes and carries by one team,
with the opponent pressing, ending in a shot or a turnover. Shot locations come from the
team's shot-distance profile and xG from a hand-tuned distance/angle formula. A Script can
force goals at given minutes and override profile values for a team over a time window.
Same inputs, same seed: identical events.
"""

from __future__ import annotations

import argparse
import math
import random
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from second_look.config import PROFILES_FILE, SEEDS_DIR
from second_look.contracts import PITCH_LENGTH_M, PITCH_WIDTH_M, Event

HALF_SECONDS = 45 * 60
GOAL_X, GOAL_Y, GOAL_WIDTH_M = PITCH_LENGTH_M, PITCH_WIDTH_M / 2, 7.32
BOX_X, BOX_Y_MIN, BOX_Y_MAX = PITCH_LENGTH_M - 16.5, 13.84, 54.16


def in_box(x: float, y: float) -> bool:
    """Inside the attacking penalty area, in the team's own frame."""
    return x >= BOX_X and BOX_Y_MIN <= y <= BOX_Y_MAX


# xG = logistic(XG_BIAS + XG_DISTANCE * distance_m + XG_ANGLE * goal_angle_rad), clamped.
# Hand-tuned so a central 11 m shot is ~0.33, 18 m ~0.10 and 27 m ~0.02.
XG_BIAS, XG_DISTANCE, XG_ANGLE = 0.4, -0.17, 1.2
XG_MIN, XG_MAX = 0.01, 0.95


def xg(distance_m: float, angle_rad: float) -> float:
    z = XG_BIAS + XG_DISTANCE * distance_m + XG_ANGLE * angle_rad
    return min(XG_MAX, max(XG_MIN, 1 / (1 + math.exp(-z))))


def goal_angle(x: float, y: float) -> float:
    """Angle (radians) the goal mouth subtends from (x, y)."""
    dx, dy = GOAL_X - x, abs(GOAL_Y - y)
    half = GOAL_WIDTH_M / 2
    return max(0.0, math.atan2(dx, dy - half) - math.atan2(dx, dy + half))


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    short: str
    colors: tuple[str, str]
    possession_bias: float  # relative weight of starting a sequence
    pass_completion: float
    long_ball_pct: float
    shot_rate: float  # chance a sequence that reaches the final third ends in a shot
    shot_distance_mean_m: float
    shot_distance_sd_m: float
    pressures_per_5min: float
    squad: tuple[str, ...] = field(default=())
    box_entry_pct: float = 1.0  # chance a pass or carry into the box gets there; else it recycles outside


def load_profiles(path: Path = PROFILES_FILE) -> dict[str, Profile]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {tid: _profile(tid, t) for tid, t in data["team"].items()}


def _profile(tid: str, t: dict) -> Profile:
    fields = {k: v for k, v in t.items() if k != "colors"}
    return Profile(id=tid, colors=tuple(t["colors"]), squad=_squad(tid), **fields)


# fmt: off
_FIRST = ("Arlo", "Bram", "Cael", "Dario", "Emre", "Finn", "Goran", "Hale", "Idris", "Jory", "Kofi",
          "Lior", "Matti", "Nils", "Otto", "Pell", "Quin", "Rafe", "Soren", "Tavi", "Ulric", "Vasco")
_LAST = ("Ashdown", "Brennick", "Callo", "Dunmore", "Elsby", "Farrow", "Gilchrist", "Holm", "Ingram",
         "Jessop", "Kettley", "Lomax", "Marlow", "Norland", "Oakes", "Pryce", "Quarry", "Rendell",
         "Sallow", "Tarrant", "Underwood", "Vance")
# fmt: on
ROLES = ("GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "RW", "ST", "LW")


def _squad(team_id: str) -> tuple[str, ...]:
    """11 fictional names, stable per team id."""
    rng = random.Random(f"squad:{team_id}")
    names: list[str] = []
    while len(names) < len(ROLES):
        name = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
        if name not in names:
            names.append(name)
    return tuple(names)


@dataclass(frozen=True)
class Override:
    team: str
    from_minute: int
    to_minute: int  # exclusive
    values: dict


@dataclass(frozen=True)
class Script:
    goals: tuple[tuple[int, str], ...] = ()  # (minute, team id); only these shots score
    overrides: tuple[Override, ...] = ()


@dataclass(frozen=True)
class SeedSpec:
    home: str
    away: str
    seed: int
    script: Script | None = None


# The demo is a two-act story: NEL hog the ball but rarely reach the box and waste long shots,
# stop pressing once YOB score at 22', attack the box after half time, and score at 78' after
# YOB lead 0-2 from few chances. Seed and settings were picked so each detector shows once or more.
DEMO_SCRIPT = Script(
    goals=((22, "yob"), (51, "yob"), (78, "nel")),
    overrides=(
        Override(
            "nel",
            0,
            35,
            {"shot_rate": 0.3, "shot_distance_mean_m": 25.0, "shot_distance_sd_m": 2.5, "box_entry_pct": 0.35},
        ),
        Override("nel", 22, 54, {"pressures_per_5min": 1.5}),  # heads drop after going behind
        Override("nel", 54, 61, {"shot_rate": 0.7, "shot_distance_mean_m": 10.5, "shot_distance_sd_m": 1.5}),
        Override("yob", 0, 61, {"shot_rate": 0.15, "shot_distance_mean_m": 22.0, "shot_distance_sd_m": 3.0}),
    ),
)

SEEDS: dict[str, SeedSpec] = {
    "demo": SeedSpec("nel", "yob", seed=21, script=DEMO_SCRIPT),
    "random1": SeedSpec("mnb", "eat", seed=26),  # unscripted; the detector makes a call that misses
    "even": SeedSpec("mer", "mnb", seed=11),
}


def simulate(home: Profile, away: Profile, seed: int, script: Script | None = None) -> list[Event]:
    return _Match(home, away, random.Random(seed), script).run()


def simulate_seed(name: str, profiles: dict[str, Profile] | None = None) -> list[Event]:
    spec = SEEDS[name]
    profiles = profiles or load_profiles()
    return simulate(profiles[spec.home], profiles[spec.away], spec.seed, spec.script)


class _Match:
    def __init__(self, home: Profile, away: Profile, rng: random.Random, script: Script | None):
        self.teams = {home.id: home, away.id: away}
        self.home, self.away = home.id, away.id
        self.rng = rng
        self.script = script
        self.pending_goals = sorted(script.goals) if script else []
        self.events: list[Event] = []
        self.t = 0.0
        self.period = 1
        self.sequence_id = 0

    def run(self) -> list[Event]:
        for period, start in ((1, 0.0), (2, float(HALF_SECONDS))):
            self.period, self.t = period, start
            self._emit("period", self.home)
            while self.t < start + HALF_SECONDS:
                self._sequence()
        return self.events

    @property
    def minute(self) -> int:
        return int(self.t // 60)

    def _profile(self, team: str) -> Profile:
        p = self.teams[team]
        for o in self.script.overrides if self.script else ():
            if o.team == team and o.from_minute <= self.minute < o.to_minute:
                p = replace(p, **o.values)
        return p

    def _emit(self, type_: str, team: str, **kw) -> None:
        self.events.append(
            Event(
                id=len(self.events),
                t=round(self.t, 1),
                minute=self.minute,
                period=self.period,
                type=type_,
                team=team,
                **kw,
            )
        )

    def _other(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def _player(self, team: str, roles: tuple[str, ...]) -> str:
        idx = self.rng.choice([i for i, r in enumerate(ROLES) if r in roles])
        return f"p_{team}_{idx + 1}"

    def _sequence(self) -> None:
        forced = self.pending_goals[0] if self.pending_goals and self.pending_goals[0][0] <= self.minute else None
        if forced:
            team = forced[1]
        else:
            h, a = self._profile(self.home), self._profile(self.away)
            team = (
                self.home
                if self.rng.random() < h.possession_bias / (h.possession_bias + a.possession_bias)
                else self.away
            )
        p, opp = self._profile(team), self._profile(self._other(team))
        self.sequence_id += 1
        seq = self.sequence_id
        self._emit("possession_start", team, sequence_id=seq)
        x, y = self.rng.uniform(20, 45), self.rng.uniform(10, PITCH_WIDTH_M - 10)
        shot_considered = False  # one shot decision per final-third entry
        while True:
            self.t += self.rng.uniform(2.5, 6.0)
            if self.rng.random() < opp.pressures_per_5min * 4.0 / 300:
                self._emit(
                    "pressure",
                    opp.id,
                    player=self._player(opp.id, ("ST", "LW", "RW", "CM")),
                    sequence_id=seq,
                    x=round(PITCH_LENGTH_M - x, 1),
                    y=round(PITCH_WIDTH_M - y, 1),
                )
            if x >= 70 and not shot_considered:
                shot_considered = True
                if forced or self.rng.random() < p.shot_rate:
                    self._shot(team, p, seq, x, y, scores=bool(forced))
                    break
            long = self.rng.random() < p.long_ball_pct
            ex = min(PITCH_LENGTH_M - 4, x + (self.rng.uniform(22, 38) if long else self.rng.uniform(4, 14)))
            ey = min(PITCH_WIDTH_M - 2, max(2.0, y + self.rng.uniform(-12, 12)))
            # Draws only when the knob is set, so seeds that never use it replay exactly.
            if p.box_entry_pct < 1.0 and in_box(ex, ey) and self.rng.random() > p.box_entry_pct:
                ex = BOX_X - self.rng.uniform(2, 8)
            completion = p.pass_completion - (0.25 if long else 0.0)
            done = forced or self.rng.random() < completion
            kind = "carry" if not long and self.rng.random() < 0.25 else "pass"
            self._emit(
                kind,
                team,
                player=self._player(team, ROLES[1:]),
                sequence_id=seq,
                x=round(x, 1),
                y=round(y, 1),
                end_x=round(ex, 1),
                end_y=round(ey, 1),
                outcome="complete" if done else "incomplete",
            )
            if not done:
                self._emit(
                    "tackle",
                    opp.id,
                    player=self._player(opp.id, ("CB", "DM", "CM", "RB", "LB")),
                    sequence_id=seq,
                    x=round(PITCH_LENGTH_M - ex, 1),
                    y=round(PITCH_WIDTH_M - ey, 1),
                    outcome="won",
                )
                break
            x, y = ex, ey
        self._emit("possession_end", team, sequence_id=seq)
        self.t += self.rng.uniform(1.0, 4.0)

    def _shot(self, team: str, p: Profile, seq: int, x: float, y: float, *, scores: bool) -> None:
        d = min(35.0, max(6.0, self.rng.gauss(p.shot_distance_mean_m, p.shot_distance_sd_m)))
        off = max(-0.6 * d, min(0.6 * d, self.rng.gauss(0, 5)))  # keep shots in front of goal
        sx, sy = GOAL_X - math.sqrt(d * d - off * off), GOAL_Y + off
        chance = xg(d, goal_angle(sx, sy))
        if scores:
            outcome = "goal"
        elif self.script:  # scripted matches score only the scripted goals
            outcome = self.rng.choice(("saved", "off_target", "blocked"))
        else:
            outcome = "goal" if self.rng.random() < chance else self.rng.choice(("saved", "off_target", "blocked"))
        self._emit(
            "shot",
            team,
            player=self._player(team, ("ST", "LW", "RW", "CM")),
            sequence_id=seq,
            x=round(sx, 1),
            y=round(sy, 1),
            outcome=outcome,
            xg=round(chance, 3),
        )
        if outcome == "goal":
            self._emit("goal", team, sequence_id=seq)
            if scores:
                self.pending_goals.pop(0)


def write_events(events: list[Event], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(e.model_dump_json(exclude_none=True) + "\n" for e in events), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="second-look-sim", description=__doc__.splitlines()[0])
    ap.add_argument("--seed-name", choices=sorted(SEEDS), help="a committed seed preset")
    ap.add_argument("--home", help="home team id (see profiles/teams.toml)")
    ap.add_argument("--away", help="away team id")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, help="events.jsonl path (default: stdout)")
    ap.add_argument("--write-seeds", action="store_true", help="regenerate every data/seeds/*/events.jsonl")
    args = ap.parse_args(argv)
    profiles = load_profiles()
    if args.write_seeds:
        for name in SEEDS:
            write_events(simulate_seed(name, profiles), SEEDS_DIR / name / "events.jsonl")
            print(f"wrote {SEEDS_DIR / name / 'events.jsonl'}")
        return 0
    if args.seed_name:
        events = simulate_seed(args.seed_name, profiles)
    elif args.home and args.away:
        events = simulate(profiles[args.home], profiles[args.away], args.seed)
    else:
        ap.error("give --seed-name, or --home and --away, or --write-seeds")
    if args.out:
        write_events(events, args.out)
    else:
        print("".join(e.model_dump_json(exclude_none=True) + "\n" for e in events), end="")
    return 0

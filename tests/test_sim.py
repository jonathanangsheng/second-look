"""Simulator: committed seeds are reproducible, every profile runs, no real club names leak."""

import re
from pathlib import Path

import pytest

from second_look.sim import SEEDS, SEEDS_DIR, load_profiles, simulate, simulate_seed, xg

ROOT = Path(__file__).resolve().parent.parent

# Distinctive real club words; whole-word match so "Village" doesn't trip "Villa".
REAL_CLUB_WORDS = (
    "arsenal", "villa", "bournemouth", "brentford", "brighton", "chelsea", "coventry", "palace",
    "everton", "fulham", "hull city", "ipswich", "leeds", "liverpool", "manchester", "man city",
    "man utd", "newcastle", "nottingham", "forest", "sunderland", "tottenham", "spurs", "hotspur",
)


@pytest.mark.parametrize("name", sorted(SEEDS))
def test_committed_seed_file_matches_a_fresh_simulation(name):
    committed = (SEEDS_DIR / name / "events.jsonl").read_text(encoding="utf-8")
    fresh = "".join(e.model_dump_json(exclude_none=True) + "\n" for e in simulate_seed(name))
    assert committed == fresh, f"data/seeds/{name} is stale: run `uv run second-look-sim --write-seeds`"


def test_same_seed_same_events_different_seed_different_events():
    p = load_profiles()
    assert simulate(p["nel"], p["yob"], 5) == simulate(p["nel"], p["yob"], 5)
    assert simulate(p["nel"], p["yob"], 5) != simulate(p["nel"], p["yob"], 6)


def test_every_profile_simulates_with_plausible_shot_volume():
    profiles = load_profiles()
    assert len(profiles) == 20
    ids = sorted(profiles)
    for i, home in enumerate(ids):
        away = ids[(i + 1) % len(ids)]
        events = simulate(profiles[home], profiles[away], i)
        for team in (home, away):
            shots = sum(1 for e in events if e.type == "shot" and e.team == team)
            assert 2 <= shots <= 30, f"{home} v {away}: {team} took {shots} shots"


def test_xg_falls_with_distance_and_stays_in_bounds():
    assert xg(6, 1.0) > xg(11, 0.6) > xg(18, 0.4) > xg(27, 0.27)
    assert 0.01 <= xg(60, 0.0) and xg(0, 3.0) <= 0.95


def test_no_real_club_names_in_data_profiles_or_web():
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in REAL_CLUB_WORDS) + r")\b", re.I)
    hits = []
    for folder in ("profiles", "data", "web"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "node_modules" not in path.parts:
                for m in pattern.finditer(path.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(f"{path.relative_to(ROOT).as_posix()}: {m.group(0)}")
    assert not hits, "\n".join(hits[:20])

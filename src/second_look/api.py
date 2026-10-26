"""HTTP API for the replay UI. Run: uv run uvicorn second_look.api:app --port 8000"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from second_look.config import CARDS_DIR, WEB_DIST
from second_look.contracts import Card
from second_look.pipeline import load_events, read_cards
from second_look.sim import SEEDS, load_profiles

app = FastAPI(title="Second Look")


@cache
def _events(seed: str) -> list[dict]:
    return [e.model_dump(exclude_none=True) for e in load_events(seed)]


@cache
def _cards(seed: str, mode: str) -> dict[tuple[int, str], Card]:
    return read_cards(seed, mode, CARDS_DIR)  # explicit: tests monkeypatch api.CARDS_DIR


def _merged(seed: str, mode: str) -> list[Card]:
    """`fail-sceptic` cards replace normal ones in the same (window, kind); the rest stay normal."""
    cards = dict(_cards(seed, "normal"))
    if mode == "fail-sceptic":
        cards.update(_cards(seed, "fail-sceptic"))
    return sorted(cards.values(), key=lambda c: c.t_start)


def _is_lie(c: Card) -> bool:
    return c.kind == "debate" and c.detector == "volume_quality"


def _is_call(c: Card) -> bool:
    return c.kind == "debate" and c.prediction_id is not None


# The moment chips in the control strip: (seed, label, mode, which card). Missing cards mean no chip.
CHIPS: tuple[tuple[str, str, str, Callable[[Card], bool]], ...] = (
    ("demo", "The lie", "normal", _is_lie),
    ("demo", "The call", "normal", _is_call),
    ("demo", "Called it", "normal", lambda c: c.kind == "called_it"),
    ("random1", "A miss", "normal", lambda c: c.kind == "missed_call"),
    ("demo", "Failure recovery", "fail-sceptic", lambda c: "cache" in c.source.values()),
)


def _team(team_id: str) -> dict:
    p = load_profiles()[team_id]
    return {"id": p.id, "name": p.name, "short": p.short, "colors": list(p.colors), "squad": list(p.squad)}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/seeds")
def seeds() -> dict:
    chips = []
    for seed, label, mode, matches in CHIPS:
        cards = _cards(seed, mode).values() if mode == "normal" else _merged(seed, mode)
        if found := sorted((c for c in cards if matches(c)), key=lambda c: c.t_start):
            chips.append(
                {
                    "label": label,
                    "seed": seed,
                    "mode": mode,
                    "t": found[0].t_start,
                    "minute": int(found[0].t_start // 60),
                }
            )
    return {
        "seeds": [{"seed": s, "home": _team(spec.home), "away": _team(spec.away)} for s, spec in SEEDS.items()],
        "chips": chips,
    }


def _known(seed: str) -> None:
    if seed not in SEEDS:
        raise HTTPException(404, f"unknown seed {seed!r}")


@app.get("/api/match/{seed}/events")
def events(seed: str) -> list[dict]:
    _known(seed)
    return _events(seed)


@app.get("/api/match/{seed}/cards")
def cards(seed: str, mode: Literal["normal", "fail-sceptic"] = "normal") -> list[Card]:
    _known(seed)
    return _merged(seed, mode)


class WebFiles(StaticFiles):
    """The built UI. index.html is revalidated on every load so a redeploy shows at once; the hashed assets it
    names can stay cached."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        if response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response


if WEB_DIST.exists():  # the built UI; in development Vite serves it and proxies /api here
    app.mount("/", WebFiles(directory=WEB_DIST, html=True), name="web")

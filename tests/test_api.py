"""Replay API: seeds and chips, events, cards with the fail-sceptic merge."""

from fastapi.testclient import TestClient

from second_look import api
from second_look.contracts import card_path

client = TestClient(api.app)


def test_seeds_list_teams_and_story_chips():
    body = client.get("/api/seeds").json()
    assert {s["seed"] for s in body["seeds"]} == {"demo", "random1", "even"}
    demo = next(s for s in body["seeds"] if s["seed"] == "demo")
    assert (demo["home"]["short"], demo["away"]["short"]) == ("NEL", "YOB")
    chips = {c["label"]: (c["seed"], c["minute"]) for c in body["chips"]}
    assert chips["The call"] == ("demo", 60) and chips["Called it"] == ("demo", 78)
    assert chips["A miss"][0] == "random1"


def test_events_and_cards_for_a_seed():
    events = client.get("/api/match/demo/events").json()
    assert events[0]["type"] == "period" and "x" not in events[0]  # nulls omitted
    cards = client.get("/api/match/demo/cards").json()
    assert [c["t_start"] for c in cards] == sorted(c["t_start"] for c in cards)


def test_unknown_seed_and_bad_mode_are_rejected():
    assert client.get("/api/match/nope/events").status_code == 404
    assert client.get("/api/match/demo/cards?mode=other").status_code == 422


def test_fail_sceptic_cards_replace_normal_ones_in_the_same_window(tmp_path, monkeypatch):
    normal = api._cards("demo", "normal")
    window, kind = next(k for k, c in normal.items() if c.kind == "debate")
    failed = normal[(window, kind)].model_copy(update={"source": {**normal[(window, kind)].source, "sceptic": "cache"}})
    for card in normal.values():
        path = card_path(tmp_path, "demo", "normal", card.window, card.kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(card.model_dump_json(), encoding="utf-8")
    path = card_path(tmp_path, "demo", "fail-sceptic", window, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(failed.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(api, "CARDS_DIR", tmp_path)
    api._cards.cache_clear()
    try:
        merged = client.get("/api/match/demo/cards?mode=fail-sceptic").json()
        assert len(merged) == len(normal)
        assert [c["source"]["sceptic"] for c in merged if c["window"] == window and c["kind"] == kind] == ["cache"]
        assert "Failure recovery" in {c["label"] for c in client.get("/api/seeds").json()["chips"]}
    finally:
        api._cards.cache_clear()

"""Cards produced from the committed seeds (planning #4 acceptance criteria)."""

import re
from collections import Counter
from functools import cache

import pytest

from second_look.contracts import Card, card_path
from second_look.pipeline import CARDS_DIR, template_cards, write_cards
from second_look.sim import SEEDS


@cache
def _cards(seed):
    return tuple(template_cards(seed))


def _debates(seed, detector):
    return [c for c in _cards(seed) if c.kind == "debate" and f"_{detector}_" in c.contradiction_id]


def test_demo_lie_card_first_fires_around_34():
    first = _debates("demo", "volume_quality")[0]
    assert first.contradiction_id.startswith("c_nel_") and 30 <= first.t_start / 60 <= 40


def test_demo_call_at_60_is_paid_off_at_78():
    call = _debates("demo", "scoreline_xg")[0]
    assert (call.t_start / 60, call.prediction_id, call.window_from_minute) == (60, "pr_nel_60", 30)
    called = [c for c in _cards("demo") if c.kind == "called_it"]
    assert [(c.prediction_id, c.evidence["minute"]) for c in called] == [("pr_nel_60", 78)]


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_every_prediction_is_resolved_by_full_time(seed):
    made = {c.prediction_id for c in _debates(seed, "scoreline_xg") if c.prediction_id}
    resolved = {c.prediction_id for c in _cards(seed) if c.kind in ("called_it", "missed_call")}
    assert made == resolved


def test_random1_shows_a_genuine_missed_call():
    assert any(c.kind == "missed_call" for c in _cards("random1"))


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_no_team_detector_pair_debates_more_than_four_times(seed):
    pairs = Counter(re.match(r"c_(\w+?)_(\w+)_\d+$", c.contradiction_id).groups() for c in _cards(seed) if c.kind == "debate")
    assert max(pairs.values(), default=0) <= 4


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_template_lines_fill_every_placeholder_and_stay_short(seed):
    for card in _cards(seed):
        for texts in [*card.lines.values(), *card.variants.values()]:
            for lang, text in texts.items():
                assert "{" not in text, text
                assert len(text.split()) <= 16, f"{lang}: {text}"


def test_live_debate_card_swaps_english_lines_only_and_records_sources():
    import asyncio
    import json

    from fakes import FakeLLM
    from second_look.pipeline import live_debate_card

    card = next(c for c in _cards("demo") if c.kind == "debate")
    llm = FakeLLM().reply(json.dumps({"line": "{team}: {shots} shots!"})).timeout().reply(json.dumps({"line": "Noise."}))
    live, flags = asyncio.run(live_debate_card(card, llm, cached=None))
    assert live.lines["hype"]["en"] == f"North East London: {card.evidence['shots']} shots!"
    assert live.lines["sceptic"]["en"] == card.lines["sceptic"]["en"]  # timed out: template
    assert (live.source["hype"], live.source["sceptic"], live.source["verdict"]) == ("live", "template", "live")
    assert live.lines["hype"]["es"] == card.lines["hype"]["es"] and live.variants == card.variants  # planning #7
    assert flags == []


def test_write_cards_keeps_existing_unless_forced(tmp_path):
    cards = list(_cards("demo"))
    assert write_cards(cards, "demo", root=tmp_path) == len(cards)
    assert write_cards(cards, "demo", root=tmp_path) == 0
    stale = card_path(tmp_path, "demo", "normal", 99, "debate")
    stale.write_text("{}")
    assert write_cards(cards, "demo", root=tmp_path, force=True) == len(cards)
    assert not stale.exists()


def test_committed_cards_are_valid_and_sit_at_their_paths():
    files = sorted(CARDS_DIR.rglob("*.json"))
    assert files
    for path in files:
        card = Card.model_validate_json(path.read_text(encoding="utf-8"))
        assert card_path(CARDS_DIR, card.seed, path.parent.name, card.window, card.kind) == path

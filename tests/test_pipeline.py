"""Cards produced from the committed seeds (planning #4 acceptance criteria)."""

import re
from collections import Counter
from functools import cache

import pytest

from second_look.config import CARDS_DIR
from second_look.contracts import Card, card_path
from second_look.pipeline import read_cards, template_cards, write_cards
from second_look.sim import SEEDS


@cache
def _cards(seed):
    return tuple(template_cards(seed))


def _debates(seed, detector):
    return [c for c in _cards(seed) if c.kind == "debate" and c.detector == detector]


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


@pytest.mark.parametrize("seed", ["demo", "random1"])
def test_outcome_cards_quote_the_claim_their_call_made(seed):
    """The quote is the prediction itself in every language: the call's template Verdict, not its live one."""
    calls = {c.prediction_id: c for c in _cards(seed) if c.kind == "debate" and c.prediction_id}
    outcomes = [c for c in _cards(seed) if c.kind in ("called_it", "missed_call")]
    assert outcomes
    for card in outcomes:
        call = calls[card.prediction_id]
        assert card.claim == call.claim == call.lines["verdict"] and card.detector == "scoreline_xg"


def test_random1_shows_a_genuine_missed_call():
    assert any(c.kind == "missed_call" for c in _cards("random1"))


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_no_team_detector_pair_debates_more_than_four_times(seed):
    pairs = Counter(
        re.match(r"c_(\w+?)_(\w+)_\d+$", c.contradiction_id).groups() for c in _cards(seed) if c.kind == "debate"
    )
    assert max(pairs.values(), default=0) <= 4


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_template_lines_fill_every_placeholder_and_stay_short(seed):
    for card in _cards(seed):
        for texts in [*card.lines.values(), *card.variants.values(), *(card.fans or {}).values()]:
            for lang, text in texts.items():
                assert "{" not in text, text
                assert len(text.split()) <= 16, f"{lang}: {text}"


@pytest.mark.parametrize("seed", ["demo", "random1"])
def test_debate_cards_have_a_fan_line_for_each_team_in_the_match(seed):
    teams = {SEEDS[seed].home, SEEDS[seed].away}
    for card in _cards(seed):
        assert (set(card.fans or {}) == teams) if card.kind == "debate" else card.fans is None


def test_live_debate_card_merges_each_piece_with_its_own_fallback():
    """Sceptic times out, Arabic fails: those keep template text; everything else ships live."""
    import asyncio
    import json

    from fakes import FakeLLM

    from second_look.pipeline import live_debate_card

    card = next(c for c in _cards("demo") if c.detector == "volume_quality")
    es = {
        "hype": "{team}: ¡{shots} tiros!",
        "verdict": "Ruido.",
        "analyst": "{shots} tiros flojos.",
        "casual": "Mucho ruido.",
        "fan_side": "Seguimos.",
        "fan_other": "Tranquilos.",
    }
    llm = (
        FakeLLM()
        .reply(json.dumps({"line": "{team}: {shots} shots!"}))
        .timeout()
        .reply(json.dumps({"line": "Noise."}))
        .reply(
            json.dumps(
                {
                    "analyst": "{shots} weak shots.",
                    "casual": "All noise.",
                    "fan_side": "We go on.",
                    "fan_other": "Calm.",
                }
            )
        )
        .reply(json.dumps(es))
    )
    live, _ = asyncio.run(live_debate_card(card, llm, cached=None, fail=frozenset({"ar"})))
    shots = card.evidence_display["shots"]["es"]
    assert live.lines["hype"]["en"] == f"North East London: {card.evidence['shots']} shots!"
    assert live.lines["hype"]["es"] == f"North East London: ¡{shots} tiros!"
    assert live.lines["sceptic"] == card.lines["sceptic"]  # timed out: template in every language
    assert live.variants["casual"] == {**card.variants["casual"], "en": "All noise.", "es": "Mucho ruido."}
    # Fan lines land on the right team: the shooting side (nel) and its opponent (yob); Arabic stays template.
    assert live.fans["nel"] == {**card.fans["nel"], "en": "We go on.", "es": "Seguimos."}
    assert live.fans["yob"] == {**card.fans["yob"], "en": "Calm.", "es": "Tranquilos."}
    assert all(live.lines[s]["ar"] == card.lines[s]["ar"] for s in live.lines)  # Arabic failed alone
    assert all(live.variants[p]["ar"] == card.variants[p]["ar"] for p in live.variants)
    assert {k: live.source[k] for k in ("hype", "sceptic", "verdict", "personaliser", "es", "ar")} == {
        "hype": "live",
        "sceptic": "template",
        "verdict": "live",
        "personaliser": "live",
        "es": "live",
        "ar": "template",
    }


def test_live_debate_card_prefers_the_cached_card_for_failed_pieces():
    import asyncio

    from fakes import FakeLLM

    from second_look.pipeline import live_debate_card

    card = next(c for c in _cards("demo") if c.kind == "debate")
    cached = card.model_copy(
        update={
            "variants": {**card.variants, "casual": {"en": "Cached.", "es": "En caché.", "ar": "مخزن."}},
            "source": {**card.source, "personaliser": "live", "es": "live", "ar": "live"},
        }
    )
    from second_look.agents import AGENTS

    live, _ = asyncio.run(live_debate_card(card, FakeLLM(), cached=cached, fail=frozenset(AGENTS)))
    assert live.variants["casual"] == cached.variants["casual"]
    assert (live.source["personaliser"], live.source["es"], live.source["ar"]) == ("cache", "cache", "cache")


def test_write_cards_keeps_existing_unless_forced(tmp_path):
    cards = list(_cards("demo"))
    assert write_cards(cards, "demo", root=tmp_path) == len(cards)
    assert write_cards(cards, "demo", root=tmp_path) == 0
    stale = card_path(tmp_path, "demo", "normal", 99, "debate")
    stale.write_text("{}")
    assert write_cards(cards, "demo", root=tmp_path, force=True) == len(cards)
    assert not stale.exists()


def test_read_cards_skips_a_truncated_file(tmp_path):
    cards = list(_cards("demo"))
    write_cards(cards, "demo", root=tmp_path)
    broken = card_path(tmp_path, "demo", "normal", cards[0].window, cards[0].kind)
    broken.write_bytes(broken.read_bytes()[:40] + b"\xd8")  # cut short mid-character
    with pytest.warns(UserWarning, match="skipping unreadable card"):
        found = read_cards("demo", "normal", tmp_path)
    assert len(found) == len(cards) - 1 and (cards[0].window, cards[0].kind) not in found


def test_committed_cards_are_valid_and_sit_at_their_paths():
    files = sorted(CARDS_DIR.rglob("*.json"))
    assert files
    for path in files:
        card = Card.model_validate_json(path.read_text(encoding="utf-8"))
        assert card_path(CARDS_DIR, card.seed, path.parent.name, card.window, card.kind) == path


def test_demo_shows_each_newer_detector_for_nel():
    """Planning #8 criterion 1, plus the effort detector: both appear as demo cards about NEL."""
    for detector in ("possession_penetration", "effort_game_state"):
        assert [c for c in _debates("demo", detector) if c.evidence["team"] == "nel"], detector


def test_even_fires_each_newer_detector_at_most_twice():
    """Planning #8 criterion 2, counted over every window boundary, picked or not."""
    from second_look import config
    from second_look.detectors import effort_game_state, possession_penetration
    from second_look.pipeline import load_events
    from second_look.stats import match_state

    spec, events = SEEDS["even"], load_events("even")
    states = [match_state(events, spec.home, spec.away, b, config.SX_WINDOW_MINUTES) for b in range(5, 91, 5)]
    for detect in (possession_penetration, effort_game_state):
        assert sum(len(detect(s)) for s in states) <= 2, detect.__name__

"""The Personaliser executor with a fake model: reply shape and per-persona word limits."""

import json

from fakes import FakeLLM
from test_agents import debate

from second_look.agents import AGENTS, VARIANT_WORDS

ONLY_PERSONALISER = frozenset(AGENTS) - {"personaliser"}


def personalise(*replies, claim=None):
    llm = FakeLLM()
    for reply in replies:
        llm.reply(reply)
    return debate(llm, fail=ONLY_PERSONALISER, speakers_only=False, claim=claim), llm


def test_personaliser_fills_both_personas_from_the_verdict():
    state, llm = personalise(json.dumps({"analyst": "{team}: {shots} shots, weak.", "casual": "Busy, not dangerous."}))
    assert state.variants == {"analyst": "NEL: 10 shots, weak.", "casual": "Busy, not dangerous."}
    assert state.source["personaliser"] == "live" and state.raw["analyst"] == "{team}: {shots} shots, weak."
    assert json.loads(llm.calls[0].user)["verdict"] == "verdict template line"


def test_personaliser_cuts_each_persona_to_its_word_limit_after_filling():
    long = "{team} " + " ".join(["word"] * 30) + "."
    state, _ = personalise(json.dumps({"analyst": long, "casual": long}))
    for persona, limit in VARIANT_WORDS.items():
        words = state.variants[persona].split()
        assert len(words) == limit and words[-1].endswith("…"), persona
        assert state.raw[persona].startswith("{team} ")  # the placeholder form is cut too, for the translators


def test_a_bad_personaliser_reply_leaves_the_variants_to_the_caller():
    state, _ = personalise("not json")
    assert state.variants == {} and "personaliser" not in state.source


CLAIM = "A goal is coming for {team}."
LONG = " ".join(["word"] * 30) + "."


def test_on_a_prediction_card_every_persona_ends_with_the_claim():
    state, _ = personalise(json.dumps({"analyst": "Chances say so.", "casual": "Busy."}), claim=CLAIM)
    assert state.variants == {
        "analyst": "Chances say so. A goal is coming for NEL.",
        "casual": "Busy. A goal is coming for NEL.",
    }
    assert state.raw["analyst"] == "Chances say so. A goal is coming for {team}."  # translators keep the placeholder


def test_an_overlong_line_on_a_prediction_card_is_retried_not_cut_before_the_claim():
    too_long, fits = (
        json.dumps({"analyst": "Fine.", "casual": LONG}),
        json.dumps({"analyst": "Fine.", "casual": "Busy."}),
    )
    state, llm = personalise(too_long, fits, claim=CLAIM)
    assert (
        state.variants["casual"] == "Busy. A goal is coming for NEL."
        and "keep each within its max_words" in llm.calls[1].user
    )
    state, _ = personalise(too_long, too_long, claim=CLAIM)
    assert state.variants == {} and "personaliser" not in state.source  # the caller keeps cached or template lines


def test_the_word_limits_and_claim_are_sent_to_the_model():
    _, llm = personalise("not json", claim=CLAIM)
    sent = json.loads(llm.calls[0].user)
    assert sent["max_words"] == VARIANT_WORDS and sent["claim"] == CLAIM  # the claim is extra, not counted

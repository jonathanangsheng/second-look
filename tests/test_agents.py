"""The debate workflow with a fake model: order, handoff, per-agent fallback, budget, fan-out/fan-in."""

import asyncio
import json

from fakes import FakeLLM

from second_look.agents import AGENTS, CALL_TIMEOUT_S, LANGUAGE, SPEAKERS, new_state, run_debate

SHOWN = {"shots": {"en": "10", "es": "10", "ar": "10"}, "team": {"en": "NEL", "es": "NEL", "ar": "NEL"}}
FALLBACK = {s: (f"{s} template line", "template") for s in ("hype", "sceptic", "verdict")}
FANS = {"fan_side": "We push.", "fan_other": "They hold."}  # the Personaliser's fan lines in a scripted reply
FANS_ES = {"fan_side": "Empujamos.", "fan_other": "Aguantan."}


def line(text):
    return json.dumps({"line": text})


LATER = frozenset(AGENTS) - set(SPEAKERS)


def debate(llm, *, fallback=FALLBACK, claim=None, budget_s=25.0, fail=frozenset(), speakers_only=True):
    """Run the workflow; by default the agents after the Verdict are forced off so tests script three replies."""
    fail = fail | LATER if speakers_only else fail

    async def go():
        return await run_debate(llm, new_state("volume_quality", SHOWN, claim, fallback, budget_s), fail=fail)

    return asyncio.run(go())


def test_agents_speak_in_order_and_each_hears_the_ones_before():
    llm = (
        FakeLLM()
        .reply(line("{shots} shots, total control."))
        .reply(line("Volume, not quality."))
        .reply(line("Lots of noise."))
    )
    state = debate(llm)
    assert state.lines == {
        "hype": "10 shots, total control.",
        "sceptic": "Volume, not quality.",
        "verdict": "Lots of noise.",
    }
    assert state.source == dict.fromkeys(("hype", "sceptic", "verdict"), "live")
    heard = [json.loads(c.user)["so_far"] for c in llm.calls]
    assert heard == [
        {},
        {"hype": "10 shots, total control."},
        {"hype": "10 shots, total control.", "sceptic": "Volume, not quality."},
    ]
    assert [c.temperature for c in llm.calls] == [0.7, 0.7, 0.3] and all(c.json for c in llm.calls)


def test_each_agent_falls_back_on_its_own():
    llm = FakeLLM().reply(line("Fine.")).reply(line("Made up 12 shots.")).reply(line("Still 12.")).timeout()
    state = debate(llm)
    assert state.source == {"hype": "live", "sceptic": "template", "verdict": "template"}
    assert state.lines["sceptic"] == "sceptic template line"


def test_a_rejected_line_gets_one_retry_told_why():
    llm = FakeLLM().reply(line("Made up 12 shots.")).reply(line("{shots} shots.")).reply(line("B.")).reply(line("C."))
    state = debate(llm)
    assert (state.lines["hype"], state.source["hype"]) == ("10 shots.", "live")
    assert "rejected: digit outside a placeholder" in llm.calls[1].user


def test_the_evidence_sent_maps_placeholders_to_shown_values():
    llm = FakeLLM().reply(line("A.")).reply(line("B.")).reply(line("C."))
    debate(llm)
    assert json.loads(llm.calls[0].user)["evidence"] == {"{shots}": "10", "{team}": "NEL"}


def test_fallback_prefers_the_cached_line():
    cached = {**FALLBACK, "sceptic": ("cached sceptic line", "cache")}
    state = debate(FakeLLM().reply(line("Fine.")).reply("not json").reply(line("Done.")), fallback=cached)
    assert (state.lines["sceptic"], state.source["sceptic"]) == ("cached sceptic line", "cache")


def test_forced_sceptic_failure_skips_its_call():
    llm = FakeLLM().reply(line("Fine.")).reply(line("Done."))  # only two replies: sceptic never calls
    state = debate(llm, fallback={**FALLBACK, "sceptic": ("cached", "cache")}, fail=frozenset({"sceptic"}))
    assert state.source == {"hype": "live", "sceptic": "cache", "verdict": "live"} and len(llm.calls) == 2


def test_call_timeouts_never_exceed_the_window_budget():
    llm = FakeLLM().reply(line("A.")).reply(line("B.")).reply(line("C."))
    debate(llm, budget_s=3.0)
    assert all(0 < c.timeout_s <= 3.0 for c in llm.calls)
    llm = FakeLLM().reply(line("A.")).reply(line("B.")).reply(line("C."))
    debate(llm)
    assert all(c.timeout_s == CALL_TIMEOUT_S for c in llm.calls)


def test_long_lines_are_cut_to_fourteen_words():
    long = " ".join(["word"] * 20) + "."
    state = debate(FakeLLM().reply(line(long)).reply(line("B.")).reply(line("C.")))
    assert len(state.lines["hype"].split()) == 14 and state.lines["hype"].endswith("…")


def test_a_failed_verdict_still_makes_the_prediction_claim():
    fallback = {**FALLBACK, "verdict": ("A goal is coming for NEL.", "template")}
    llm = FakeLLM().reply(line("A.")).reply(line("B.")).timeout()
    state = debate(llm, fallback=fallback, claim="A goal is coming for {team}.")
    assert state.lines["verdict"] == "A goal is coming for NEL."
    assert json.loads(llm.calls[2].user)["claim"] == "A goal is coming for {team}."


def test_five_agents_hand_off_and_fan_in_survives_one_failed_translator():
    llm = (
        FakeLLM()
        .reply(line("{shots} shots."))
        .reply(line("Volume."))
        .reply(line("Noise."))
        .reply(json.dumps({"analyst": "{shots} shots, low quality.", "casual": "Lots of shots, few chances.", **FANS}))
        .reply(
            json.dumps(
                {
                    "hype": "{shots} tiros.",
                    "sceptic": "Volumen.",
                    "verdict": "Ruido.",
                    "analyst": "{shots} tiros, poca calidad.",
                    "casual": "Muchos tiros.",
                    **FANS_ES,
                }
            )
        )
    )
    state = debate(llm, fail=frozenset({"ar"}), speakers_only=False)
    assert state.variants == {"analyst": "10 shots, low quality.", "casual": "Lots of shots, few chances.", **FANS}
    assert state.translations == {
        "es": {
            "hype": "10 tiros.",
            "sceptic": "Volumen.",
            "verdict": "Ruido.",
            "analyst": "10 tiros, poca calidad.",
            "casual": "Muchos tiros.",
            **FANS_ES,
        }
    }
    assert state.source == {"hype": "live", "sceptic": "live", "verdict": "live", "personaliser": "live", "es": "live"}
    assert json.loads(llm.calls[3].user)["verdict"] == "Noise."
    assert json.loads(llm.calls[4].user) == {"language": LANGUAGE["es"], "lines": state.raw}


def test_a_translation_that_drops_a_placeholder_fails_its_language_after_one_retry():
    dropped = json.dumps({"hype": "Muchos tiros."})
    llm = FakeLLM().reply(line("{shots} shots.")).reply(dropped).reply(dropped)
    state = debate(llm, fail=frozenset({"sceptic", "verdict", "personaliser", "es"}), speakers_only=False)
    assert "ar" not in state.source and state.translations == {} and len(llm.calls) == 3
    assert "placeholders changed" in llm.calls[2].user


def test_a_spent_window_budget_skips_every_call():
    llm = FakeLLM()
    state = debate(llm, budget_s=0, speakers_only=False)
    assert llm.calls == [] and state.source == dict.fromkeys(("hype", "sceptic", "verdict"), "template")


def test_a_team_name_typed_out_is_rejected_so_translators_never_see_it():
    llm = FakeLLM().reply(line("NEL take {shots} shots.")).reply(line("{team} take {shots} shots."))
    state = debate(llm, fail=frozenset({"sceptic", "verdict"}))
    assert state.raw["hype"] == "{team} take {shots} shots." and "write {team} instead of 'NEL'" in llm.calls[1].user


def test_the_join_merges_each_translator_branch_even_from_separate_copies():
    import copy

    from second_look.agents import _merge

    async def go():
        base = new_state("volume_quality", SHOWN, None, FALLBACK)
        base.source = {"hype": "live"}
        es, ar = copy.deepcopy(base), copy.deepcopy(base)
        es.translations, es.source["es"] = {"es": {"hype": "Hola."}}, "live"
        ar.translations, ar.source["ar"] = {"ar": {"hype": "مرحبا."}}, "live"
        return _merge([es, ar])

    merged = asyncio.run(go())
    assert merged.translations == {"es": {"hype": "Hola."}, "ar": {"hype": "مرحبا."}}
    assert merged.source == {"hype": "live", "es": "live", "ar": "live"}


def test_a_ratio_limit_is_kept_from_the_agents():
    shown = {
        **SHOWN,
        "ratio": {"en": "0.4", "es": "0,4", "ar": "0.4"},
        "max_ratio": {"en": "0.6", "es": "0,6", "ar": "0.6"},
    }
    llm = FakeLLM().reply(line("A.")).reply(line("B.")).reply(line("C."))

    async def go():
        return await run_debate(llm, new_state("volume_quality", shown, None, FALLBACK), fail=LATER)

    asyncio.run(go())
    sent = json.loads(llm.calls[0].user)["evidence"]
    assert "{ratio}" in sent and "{max_ratio}" not in sent

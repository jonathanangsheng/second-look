"""The debate workflow with a fake model: order, handoff, per-agent fallback, budget."""

import asyncio
import json

from fakes import FakeLLM

from second_look.agents import CALL_TIMEOUT_S, new_state, run_debate

SHOWN = {"shots": {"en": "10", "es": "10", "ar": "10"}, "team": {"en": "NEL", "es": "NEL", "ar": "NEL"}}
FALLBACK = {s: (f"{s} template line", "template") for s in ("hype", "sceptic", "verdict")}


def line(text):
    return json.dumps({"line": text})


def debate(llm, *, fallback=FALLBACK, claim=None, budget_s=25.0, fail=frozenset()):
    async def go():
        return await run_debate(
            llm, new_state("volume_quality", {"shots": 10}, SHOWN, claim, fallback, budget_s), fail=fail
        )

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
    llm = FakeLLM().reply(line("Fine.")).reply(line("Made up 12 shots.")).timeout()
    state = debate(llm)
    assert state.source == {"hype": "live", "sceptic": "template", "verdict": "template"}
    assert state.lines["sceptic"] == "sceptic template line"


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
    state = debate(llm, fallback=fallback, claim="A goal is coming for NEL.")
    assert state.lines["verdict"] == "A goal is coming for NEL."
    assert json.loads(llm.calls[2].user)["claim"] == "A goal is coming for NEL."

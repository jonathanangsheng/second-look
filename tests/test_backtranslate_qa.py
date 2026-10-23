"""scripts/backtranslate_qa.py with a fake model: flags changed meanings and keeps review notes."""

import asyncio
import importlib.util
import json

from fakes import FakeLLM

from second_look.config import ROOT
from second_look.pipeline import template_cards

_spec = importlib.util.spec_from_file_location("backtranslate_qa", ROOT / "scripts" / "backtranslate_qa.py")
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)


def test_only_changed_strings_are_flagged_per_language():
    card = next(c for c in template_cards("demo") if c.kind == "debate")
    same = {p: {"back": "x", "meaning": "same"} for p in (*card.lines, *card.variants)}
    llm = (
        FakeLLM()
        .reply(json.dumps({**same, "casual": {"back": "Wrong.", "meaning": "changed"}}))
        .reply(json.dumps(same))
    )
    flags = asyncio.run(qa.review(llm, "demo/normal/06-debate.json", card))
    assert [f["id"] for f in flags] == ["demo/normal/06-debate.json es casual"]
    assert flags[0]["translated"] == card.variants["casual"]["es"] and flags[0]["back"] == "Wrong."
    assert "Spanish" in llm.calls[0].system and "Arabic" in llm.calls[1].system


def test_a_rerun_keeps_the_notes_of_strings_still_flagged():
    flag = {"id": "demo/normal/06-debate.json ar hype", "en": "A.", "translated": "ب.", "back": "B."}
    old = qa.render([flag], 9).replace("Note: \n", "Note: accepted, idiom\n")
    assert "Note: accepted, idiom" in qa.render([flag], 9, old)
    assert "Note: \n" in qa.render([{**flag, "id": "other"}], 9, old)


def test_a_string_the_model_leaves_out_is_flagged():
    card = next(c for c in template_cards("demo") if c.kind == "debate")
    same = {p: {"back": "x", "meaning": "same"} for p in (*card.lines, *card.variants)}
    del same["analyst"]
    llm = FakeLLM().reply(json.dumps(same)).reply(json.dumps({**same, "analyst": "not a dict"}))
    flags = asyncio.run(qa.review(llm, "c.json", card))
    assert [(f["id"], f["back"]) for f in flags] == [
        ("c.json es analyst", "(missing from the reply)"),
        ("c.json ar analyst", "(missing from the reply)"),
    ]


def test_cards_that_could_not_be_checked_are_listed():
    assert "Not checked, rerun: demo/normal/06-debate.json" in qa.render(
        [], 13, unchecked=("demo/normal/06-debate.json",)
    )

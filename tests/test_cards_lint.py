"""Every committed card follows the rules the real model output must keep (eng review D7).

Unit tests use a fake model, so this is the check on what actually ships. Word limits apply to
English only; Spanish and Arabic run longer and are not cut. On prediction cards the claim
sentence appended to each persona line does not count toward its limit. Real club names are covered by
test_sim and the employer term by test_repo_lint; both scan cards/.
"""

import re

import pytest

from second_look.agents import MAX_WORDS, VARIANT_WORDS
from second_look.config import CARDS_DIR
from second_look.contracts import Card
from second_look.grounding import ARABIC_INDIC

CARD_FILES = sorted(CARDS_DIR.rglob("*.json"))
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return set(NUMBER.findall(text.translate(ARABIC_INDIC)))


@pytest.mark.parametrize("path", CARD_FILES, ids=lambda p: p.relative_to(CARDS_DIR).as_posix())
def test_committed_card_follows_the_text_rules(path):
    card = Card.model_validate_json(path.read_text(encoding="utf-8"))
    limits = {**dict.fromkeys(card.lines, MAX_WORDS), **VARIANT_WORDS}
    if card.kind == "debate" and card.claim:  # the claim sentence appended to each persona line is extra
        claim_words = len(card.claim["en"].split())
        limits = {k: n + claim_words if k in VARIANT_WORDS else n for k, n in limits.items()}
    for name, texts in [*card.lines.items(), *card.variants.items()]:
        for lang, text in texts.items():
            where = f"{name}.{lang}: {text}"
            assert text.strip(), where
            if lang == "en":
                assert len(text.split()) <= limits[name], where
            shown = set().union(*(_numbers(v[lang]) for v in card.evidence_display.values()))
            assert _numbers(text) <= shown, f"digit not in evidence: {where}"


def test_there_are_committed_cards_to_lint():
    assert CARD_FILES

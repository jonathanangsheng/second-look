"""Numbers in agent text only through evidence placeholders."""

import pytest

from second_look.grounding import GroundingError, ground, number_words

SHOWN = {
    "shots": {"en": "10", "es": "10", "ar": "10"},
    "xg_per_shot": {"en": "0.05", "es": "0,05", "ar": "0.05"},
    "team": {"en": "North East London", "es": "North East London", "ar": "North East London"},
}


def test_placeholders_are_filled_per_language():
    assert (
        ground("{team}: {shots} shots at {xg_per_shot} each.", SHOWN, "es")
        == "North East London: 10 shots at 0,05 each."
    )


@pytest.mark.parametrize(
    "raw",
    ["{shots} shots, 12 on target.", "only ٣ chances", "0.05 per shot"],
    ids=["digit", "arabic-indic", "invented-xg"],
)
def test_any_digit_outside_a_placeholder_is_rejected(raw):
    with pytest.raises(GroundingError, match="digit"):
        ground(raw, SHOWN, "en")


def test_unknown_placeholder_and_broken_braces_are_rejected():
    with pytest.raises(GroundingError, match="unknown"):
        ground("{goals} goals", SHOWN, "en")
    with pytest.raises(GroundingError):
        ground("{shots shots", SHOWN, "en")


def test_spelled_numbers_are_flagged_not_rejected():
    text = ground("No one is tracking back, two shots from {shots}.", SHOWN, "en")
    assert number_words(text, "en") == ["one", "two"]

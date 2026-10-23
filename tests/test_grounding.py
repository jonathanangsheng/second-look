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


@pytest.mark.parametrize("raw", ["North East London take {shots} shots.", "north east london take {shots} shots."])
def test_a_team_name_typed_out_is_rejected(raw):
    with pytest.raises(GroundingError, match=r"write \{team\} instead"):
        ground(raw, SHOWN, "en")


def test_a_team_name_inside_a_longer_word_and_digit_values_are_not_names():
    shown = {**SHOWN, "team": {"en": "Leeds", "es": "Leeds", "ar": "Leeds"}}
    assert ground("Leedsfield fans see {shots} shots at {xg_per_shot}.", shown, "en").startswith("Leedsfield")


def test_digits_inside_a_placeholder_name_are_not_a_number():
    shown = {**SHOWN, "rate_per_10": {"en": "6.4", "es": "6,4", "ar": "6.4"}}
    assert ground("Only {rate_per_10} box entries.", shown, "en") == "Only 6.4 box entries."
    with pytest.raises(GroundingError):
        ground("Only {rate_per_10} box entries per 10.", shown, "en")

"""The shared contracts accept the fixtures and reject malformed data."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from second_look.contracts import Card, Event, Prediction, card_path

FIXTURES = Path(__file__).parent / "fixtures"
CARD_FILES = sorted((FIXTURES / "cards").rglob("*.json"))


def test_fixture_cards_exist():
    assert len(CARD_FILES) >= 5


@pytest.mark.parametrize("path", CARD_FILES, ids=lambda p: p.relative_to(FIXTURES).as_posix())
def test_fixture_card_validates_and_sits_at_its_cache_path(path):
    card = Card.model_validate_json(path.read_text(encoding="utf-8"))
    mode = path.parent.name
    assert card_path(FIXTURES / "cards", card.seed, mode, card.window, card.kind) == path


def test_fixture_events_validate():
    lines = (FIXTURES / "events" / "sample.jsonl").read_text(encoding="utf-8").splitlines()
    events = [Event.model_validate(json.loads(line)) for line in lines if line.strip()]
    assert [e.id for e in events] == sorted(e.id for e in events)


def _event(**overrides):
    base = {
        "id": 1,
        "t": 1.0,
        "minute": 0,
        "period": 1,
        "type": "pass",
        "team": "nel",
        "x": 50.0,
        "y": 30.0,
        "end_x": 60.0,
        "end_y": 30.0,
    }
    return {**base, **overrides}


def test_pass_without_end_location_is_rejected():
    with pytest.raises(ValidationError, match="end_x"):
        Event.model_validate(_event(end_x=None))


def test_shot_without_xg_is_rejected():
    with pytest.raises(ValidationError, match="xg"):
        Event.model_validate(_event(type="shot", end_x=None, end_y=None))


def test_shot_without_location_is_rejected():
    with pytest.raises(ValidationError, match="x and y"):
        Event.model_validate(_event(type="shot", xg=0.1, x=None, end_x=None, end_y=None))


def test_coordinates_outside_the_pitch_are_rejected():
    with pytest.raises(ValidationError):
        Event.model_validate(_event(x=106.0))


@pytest.mark.parametrize(("made_at", "by"), [(60, 85), (70, 90), (89, 90)])
def test_prediction_deadline_is_made_at_plus_25_capped_at_full_time(made_at, by):
    Prediction(id="p", team="nel", made_at_minute=made_at, by_minute=by, claim_text="x")


def test_prediction_with_wrong_deadline_is_rejected():
    with pytest.raises(ValidationError, match="by_minute"):
        Prediction(id="p", team="nel", made_at_minute=70, by_minute=95, claim_text="x")


def _card_dict():
    return json.loads((FIXTURES / "cards" / "demo" / "normal" / "06-debate.json").read_text(encoding="utf-8"))


def test_card_missing_a_language_is_rejected():
    data = _card_dict()
    del data["lines"]["sceptic"]["ar"]
    with pytest.raises(ValidationError, match="missing languages"):
        Card.model_validate(data)


def test_debate_card_needs_all_three_speakers():
    data = _card_dict()
    del data["lines"]["hype"]
    with pytest.raises(ValidationError, match="hype, sceptic and verdict"):
        Card.model_validate(data)


def test_outcome_card_must_reference_a_prediction():
    data = json.loads((FIXTURES / "cards" / "demo" / "normal" / "15-called_it.json").read_text(encoding="utf-8"))
    data["prediction_id"] = None
    with pytest.raises(ValidationError, match="prediction"):
        Card.model_validate(data)

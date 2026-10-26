"""Shared data contracts. Source of truth for the simulator, pipeline, API and web UI.

Mirrored in web/src/contracts.ts. Change both, plus tests/fixtures, in one commit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Lang = Literal["en", "es", "ar"]
Persona = Literal["analyst", "casual"]
Speaker = Literal["hype", "sceptic", "verdict"]
Source = Literal["live", "cache", "template"]
CacheMode = Literal["normal", "fail-sceptic"]

EventType = Literal[
    "pass",
    "carry",
    "shot",
    "pressure",
    "tackle",
    "possession_start",
    "possession_end",
    "goal",
    "period",
]
Outcome = Literal["complete", "incomplete", "saved", "blocked", "off_target", "goal", "won", "lost"]
Detector = Literal["volume_quality", "possession_penetration", "scoreline_xg", "effort_game_state"]

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
FULL_TIME_MINUTE = 90
PREDICTION_HORIZON_MIN = 25


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Event(_Strict):
    """One synthetic match event. Coordinates in metres, attacking left to right for `team`."""

    id: int = Field(ge=0)
    t: float = Field(ge=0, description="seconds since kick-off")
    minute: int = Field(ge=0, le=FULL_TIME_MINUTE + 10)
    period: Literal[1, 2]
    type: EventType
    team: str
    player: str | None = None
    sequence_id: int | None = None
    x: float | None = Field(default=None, ge=0, le=PITCH_LENGTH_M)
    y: float | None = Field(default=None, ge=0, le=PITCH_WIDTH_M)
    end_x: float | None = Field(default=None, ge=0, le=PITCH_LENGTH_M)
    end_y: float | None = Field(default=None, ge=0, le=PITCH_WIDTH_M)
    outcome: Outcome | None = None
    xg: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _type_fields(self) -> Event:
        if self.type in ("pass", "carry") and (self.end_x is None or self.end_y is None):
            raise ValueError(f"{self.type} events need end_x and end_y")
        if self.type == "shot" and (self.xg is None or self.x is None or self.y is None):
            raise ValueError("shot events need xg, x and y")
        return self


class StatValue(_Strict):
    label: str
    value: float


class Contradiction(_Strict):
    id: str
    detector: Detector
    team: str
    minute: int = Field(ge=0, le=FULL_TIME_MINUTE + 10)
    surface: StatValue
    truth: StatValue
    evidence: dict[str, float | int | str]
    # One pre-formatted string per evidence field and language (e.g. ES decimal comma).
    evidence_display: dict[str, dict[Lang, str]]
    severity: float = Field(ge=0, le=1)
    prediction_id: str | None = None
    # Start of the rolling window the detector measured (scoreline_xg), shown as "Since 30'".
    window_from_minute: int | None = None


class Prediction(_Strict):
    id: str
    team: str = Field(description="the trailing team, ahead on xG")
    event_type: Literal["goal"] = "goal"
    made_at_minute: int = Field(ge=0, le=FULL_TIME_MINUTE)
    by_minute: int = Field(ge=0, le=FULL_TIME_MINUTE)
    claim_text: str
    status: Literal["open", "fulfilled", "expired"] = "open"

    @model_validator(mode="after")
    def _deadline(self) -> Prediction:
        expected = min(self.made_at_minute + PREDICTION_HORIZON_MIN, FULL_TIME_MINUTE)
        if self.by_minute != expected:
            raise ValueError(f"by_minute must be {expected} (made_at + {PREDICTION_HORIZON_MIN}, capped at full time)")
        return self


LangText = dict[Lang, str]


class Card(_Strict):
    """One overlay card, stored at cards/{seed}/{mode}/{window}.json."""

    seed: str
    window: int = Field(ge=0)
    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    kind: Literal["debate", "called_it", "missed_call"]
    detector: Detector  # outcome cards carry their call's detector, scoreline_xg
    contradiction_id: str | None = None
    prediction_id: str | None = None
    window_from_minute: int | None = None
    claim: LangText | None = None  # the prediction, on a call's debate card and its outcome card
    lines: dict[Speaker, LangText]
    # The Verdict line shown on screen is variants[persona][lang]; Hype and Sceptic never change.
    variants: dict[Persona, LangText]
    # The Verdict for a viewer who supports a team: team id -> line, on debate cards.
    fans: dict[str, LangText] | None = None
    source: dict[Literal["hype", "sceptic", "verdict", "personaliser", "es", "ar"], Source]
    evidence: dict[str, float | int | str]
    evidence_display: dict[str, LangText] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _complete(self) -> Card:
        if self.t_end < self.t_start:
            raise ValueError("t_end must be >= t_start")
        langs = {"en", "es", "ar"}
        texts_by_name = [*self.lines.items(), *self.variants.items()]
        if self.claim:
            texts_by_name.append(("claim", self.claim))
        texts_by_name += [(f"fans.{team}", texts) for team, texts in (self.fans or {}).items()]
        for name, texts in texts_by_name:
            missing = langs - texts.keys()
            if missing:
                raise ValueError(f"{name} is missing languages: {sorted(missing)}")
        if self.kind == "debate" and set(self.lines) != {"hype", "sceptic", "verdict"}:
            raise ValueError("debate cards need hype, sceptic and verdict lines")
        if set(self.variants) != {"analyst", "casual"}:
            raise ValueError("cards need analyst and casual variants")
        if self.kind != "debate" and self.prediction_id is None:
            raise ValueError(f"{self.kind} cards must reference a prediction")
        if (self.prediction_id is None) != (self.claim is None):
            raise ValueError("a card has a claim exactly when it references a prediction")
        return self


def card_path(root: Path, seed: str, mode: CacheMode, window: int, kind: str) -> Path:
    """Cache location for one card. A debate and an outcome card can share a window."""
    return root / seed / mode / f"{window:02d}-{kind}.json"

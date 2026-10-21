"""Walk a seed's events window by window and produce overlay cards, plus card cache I/O."""

from __future__ import annotations

import shutil
from pathlib import Path

from second_look import config, templates
from second_look.contracts import FULL_TIME_MINUTE, Card, CacheMode, Contradiction, Event, Prediction, card_path
from second_look.detectors import Picker, run_all
from second_look.ledger import Ledger
from second_look.sim import ROOT, SEEDS, SEEDS_DIR, load_profiles
from second_look.stats import match_state

CARDS_DIR = ROOT / "cards"
CARD_SECONDS = 12


def load_events(seed: str) -> list[Event]:
    lines = (SEEDS_DIR / seed / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [Event.model_validate_json(line) for line in lines if line]


def template_cards(seed: str) -> list[Card]:
    """Every card for a seed with deterministic template text, in time order."""
    spec = SEEDS[seed]
    events = load_events(seed)
    names = {tid: p.name for tid, p in load_profiles().items()}
    ledger, picker, cards = Ledger(), Picker(), []

    for boundary in range(config.WINDOW_MINUTES, FULL_TIME_MINUTE + 1, config.WINDOW_MINUTES):
        for goal in (e for e in events if e.type == "goal" and boundary - config.WINDOW_MINUTES <= e.minute < boundary):
            if fulfilled := ledger.goal(goal.team, goal.minute):
                cards.append(_outcome_card(seed, "called_it", fulfilled, goal.minute, goal.t, names))
        for expired in ledger.expire(boundary, full_time=boundary == FULL_TIME_MINUTE):
            cards.append(_outcome_card(seed, "missed_call", expired, boundary, boundary * 60.0, names))
        if boundary == FULL_TIME_MINUTE:
            break  # no debate at the final whistle
        state = match_state(events, spec.home, spec.away, boundary, config.SX_WINDOW_MINUTES)
        found = run_all(state)
        predicts = {c.id for c in found if c.detector == "scoreline_xg" and not ledger.has_open(c.team)}
        if chosen := picker.pick(found, predicts):
            prediction = None
            if chosen.id in predicts:
                claim = templates.TEMPLATES["scoreline_xg"]["verdict"]["en"].format(team=names[chosen.team])
                prediction = ledger.make(chosen.team, boundary, claim)
            cards.append(_debate_card(seed, chosen, prediction, names))
    return sorted(cards, key=lambda c: c.t_start)


def _debate_card(seed: str, c: Contradiction, prediction: Prediction | None, names: dict[str, str]) -> Card:
    lines, variants, shown = templates.render(c.detector, c.evidence, names)
    return Card(
        seed=seed, window=c.minute // config.WINDOW_MINUTES - 1, t_start=c.minute * 60.0,
        t_end=c.minute * 60.0 + CARD_SECONDS, kind="debate", contradiction_id=c.id,
        prediction_id=prediction.id if prediction else None, window_from_minute=c.window_from_minute,
        lines=lines, variants=variants, source=_all_template(lines), evidence=c.evidence, evidence_display=shown,
    )


def _outcome_card(seed: str, kind: str, p: Prediction, minute: int, t: float, names: dict[str, str]) -> Card:
    evidence = {"team": p.team, "made_at_minute": p.made_at_minute, "by_minute": p.by_minute, "minute": minute}
    lines, variants, shown = templates.render(kind, evidence, names)
    window = min(minute, FULL_TIME_MINUTE - 1) // config.WINDOW_MINUTES
    return Card(
        seed=seed, window=window, t_start=t, t_end=t + CARD_SECONDS, kind=kind,
        contradiction_id=f"c_{p.team}_scoreline_xg_{p.made_at_minute}", prediction_id=p.id,
        lines=lines, variants=variants, source=_all_template(lines), evidence=evidence, evidence_display=shown,
    )


def _all_template(lines: dict) -> dict:
    return {**dict.fromkeys(lines, "template"), "personaliser": "template", "es": "template", "ar": "template"}


def write_cards(cards: list[Card], seed: str, mode: CacheMode = "normal", root: Path = CARDS_DIR, force: bool = False) -> int:
    """Write cards to the cache. Existing files are kept unless `force` (which clears the seed/mode folder first)."""
    folder = root / seed / mode
    if force and folder.exists():
        shutil.rmtree(folder)
    written = 0
    for card in cards:
        path = card_path(root, seed, mode, card.window, card.kind)
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(card.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written += 1
    return written

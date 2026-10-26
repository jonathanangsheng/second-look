"""Walk a seed's events window by window and produce overlay cards, plus card cache I/O."""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

from pydantic import ValidationError

from second_look import config, templates
from second_look.config import CARDS_DIR, SEEDS_DIR
from second_look.contracts import FULL_TIME_MINUTE, CacheMode, Card, Contradiction, Event, Prediction, card_path
from second_look.detectors import Picker, run_all
from second_look.ledger import Ledger
from second_look.sim import SEEDS, load_profiles
from second_look.stats import match_state

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
            prediction, claim = None, None
            if chosen.id in predicts:
                claim = templates.claim(names[chosen.team])
                prediction = ledger.make(chosen.team, boundary, claim["en"])
            cards.append(_debate_card(seed, chosen, prediction, claim, names))
    return sorted(cards, key=lambda c: c.t_start)


def _debate_card(
    seed: str, c: Contradiction, prediction: Prediction | None, claim: templates.T | None, names: dict[str, str]
) -> Card:
    lines, variants, shown, fans = templates.render(c.detector, c.evidence, names)
    return Card(
        seed=seed,
        window=c.minute // config.WINDOW_MINUTES - 1,
        t_start=c.minute * 60.0,
        t_end=c.minute * 60.0 + CARD_SECONDS,
        kind="debate",
        detector=c.detector,
        contradiction_id=c.id,
        prediction_id=prediction.id if prediction else None,
        window_from_minute=c.window_from_minute,
        claim=claim,
        lines=lines,
        variants=variants,
        fans={team: fans[side] for side, team in _fan_teams(seed, c.team).items()},
        source=_all_template(lines),
        evidence=c.evidence,
        evidence_display=shown,
    )


def _outcome_card(seed: str, kind: str, p: Prediction, minute: int, t: float, names: dict[str, str]) -> Card:
    evidence = {"team": p.team, "made_at_minute": p.made_at_minute, "by_minute": p.by_minute, "minute": minute}
    lines, variants, shown, _ = templates.render(kind, evidence, names)
    window = min(minute, FULL_TIME_MINUTE - 1) // config.WINDOW_MINUTES
    return Card(
        seed=seed,
        window=window,
        t_start=t,
        t_end=t + CARD_SECONDS,
        kind=kind,
        detector="scoreline_xg",
        contradiction_id=f"c_{p.team}_scoreline_xg_{p.made_at_minute}",
        prediction_id=p.id,
        claim=templates.claim(names[p.team]),  # the prediction as made, quoted by the outcome card
        lines=lines,
        variants=variants,
        source=_all_template(lines),
        evidence=evidence,
        evidence_display=shown,
    )


def _fan_teams(seed: str, team: str) -> dict[str, str]:
    """Fan perspective -> team id: the team the stat is about (shooter or trailer), and its opponent."""
    spec = SEEDS[seed]
    return {"fan_side": team, "fan_other": spec.away if team == spec.home else spec.home}


def _all_template(lines: dict) -> dict:
    return {**dict.fromkeys(lines, "template"), "personaliser": "template", "es": "template", "ar": "template"}


async def live_debate_card(
    card: Card, llm, cached: Card | None, fail: frozenset[str] = frozenset()
) -> tuple[Card, list[str]]:
    """Run the agents over a template debate card and merge whatever came back live.

    Every piece falls back on its own, with its true source: a speaker line, the persona and
    fan variants (Personaliser) and each language (Translator) keep the cached card's text if
    there is one, else the template's.
    """
    from second_look.agents import AGENTS, SPEAKERS, new_state, run_debate

    def fallback_source(piece: str) -> str:
        return "cache" if cached and cached.source.get(piece, "template") != "template" else "template"

    base = cached or card
    fallback = {s: (base.lines[s]["en"], fallback_source(s)) for s in SPEAKERS}
    claim = templates.CLAIM["en"] if card.claim else None  # placeholder form, for the agents
    state = await run_debate(llm, new_state(card.detector, card.evidence_display, claim, fallback), fail=fail)
    lines = {s: {**base.lines[s], "en": state.lines[s]} for s in SPEAKERS}
    variants = {p: dict(texts) for p, texts in base.variants.items()}
    fans = {team: dict(texts) for team, texts in (base.fans or card.fans).items()}
    subject = card.evidence.get("trailer") or card.evidence["team"]
    # Every piece by the name the agents use, pointing at the card text it updates.
    pieces = {**lines, **variants, **{side: fans[team] for side, team in _fan_teams(card.seed, subject).items()}}
    for piece, text in state.variants.items():
        pieces[piece]["en"] = text
    for lang, translated in state.translations.items():
        for piece, text in translated.items():
            pieces[piece][lang] = text
    source = {**card.source, **{k: fallback_source(k) for k in AGENTS}, **state.source}
    update = {"lines": lines, "variants": variants, "fans": fans, "source": source}
    return card.model_copy(update=update), state.flags


def read_cards(seed: str, mode: CacheMode, root: Path = CARDS_DIR, strict: bool = False) -> dict[tuple[int, str], Card]:
    """Cached cards for a seed and mode, keyed by (window, kind). Empty if none are cached.

    An unreadable file (e.g. cut short by an interrupted write) is skipped with a warning, so a live build redoes it;
    `strict` raises instead, for serving.
    """
    cards = {}
    for path in sorted((root / seed / mode).glob("*.json")):
        try:
            card = Card.model_validate_json(path.read_bytes())  # bytes: a cut-off UTF-8 character is invalid JSON too
        except ValidationError as exc:
            if strict:
                raise ValueError(f"unreadable card {path}") from exc
            warnings.warn(f"skipping unreadable card {path}: {exc.error_count()} error(s)", stacklevel=2)
            continue
        cards[card.window, card.kind] = card
    return cards


def write_cards(
    cards: list[Card], seed: str, mode: CacheMode = "normal", root: Path = CARDS_DIR, force: bool = False
) -> int:
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

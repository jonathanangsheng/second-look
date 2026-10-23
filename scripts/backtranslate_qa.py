"""Back-translate every committed Spanish and Arabic card string and flag meaning changes.

Usage: uv run python scripts/backtranslate_qa.py

One model call per card and language: translate each string back to English without seeing
the original, then compare it with the English and answer same|changed. Flagged strings go to
qa/backtranslate.md; review each one and write a note under it (fixed, or accepted and why).
A rerun keeps the notes of strings that are still flagged.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys

from second_look.agents import LANGUAGE
from second_look.config import CARDS_DIR, ROOT
from second_look.contracts import Card
from second_look.llm import LLM, LLMError, LLMUnavailable

REPORT = ROOT / "qa" / "backtranslate.md"
SYSTEM = """You check translations of football broadcast overlay lines. You get a JSON object whose values each have
"translated" (a {language} line) and "english" (the line it was translated from).
For each key: first translate "translated" back into English on your own, as literally as reads naturally, then
compare that with "english". Answer "changed" if a fact, number placeholder, team, direction of the claim or tone
differs; otherwise "same". {{placeholders}} stand for numbers and names and must match.
Reply with JSON only: {{"<key>": {{"back": "<your English>", "meaning": "same|changed"}}, ...}}"""


async def review(llm, name: str, card: Card) -> list[dict]:
    """Flagged strings of one card: [{id, en, translated, back}]."""
    flagged, texts = [], {**card.lines, **card.variants, **{f"fan_{t}": v for t, v in (card.fans or {}).items()}}
    for lang, language in LANGUAGE.items():
        pieces = {piece: {"translated": t[lang], "english": t["en"]} for piece, t in texts.items()}
        reply = await llm.complete(
            SYSTEM.format(language=language),
            json.dumps(pieces, ensure_ascii=False),
            temperature=0.0,
            max_tokens=1200,
            timeout_s=30.0,
            json=True,
        )
        verdicts = json.loads(reply)
        for piece, pair in pieces.items():  # a piece the model left out is flagged, not assumed fine
            verdict = verdicts.get(piece)
            if not isinstance(verdict, dict) or verdict.get("meaning") != "same":
                back = verdict.get("back", "") if isinstance(verdict, dict) else "(missing from the reply)"
                flagged.append(
                    {
                        "id": f"{name} {lang} {piece}",
                        "en": pair["english"],
                        "translated": pair["translated"],
                        "back": back,
                    }
                )
    return flagged


def render(flags: list[dict], checked: int, old: str = "", unchecked: tuple[str, ...] = ()) -> str:
    """The report, carrying over the Note line of every entry that is flagged again."""
    notes = dict(re.findall(r"^### (.+)\n(?:.*\n)*?Note: (.*)$", old, re.M))
    out = [
        "# Back-translation QA",
        "",
        f"{checked} cards checked, {len(flags)} strings flagged. Review each and fill in its Note (one line).",
    ]
    if unchecked:
        out += ["", f"Not checked, rerun: {', '.join(unchecked)}"]
    for f in flags:
        out += ["", f"### {f['id']}", f"- English: {f['en']}", f"- Translated: {f['translated']}",
                f"- Back-translated: {f['back']}", f"Note: {notes.get(f['id'], '')}"]  # fmt: skip
    return "\n".join(out) + "\n"


async def main() -> int:
    try:
        llm = LLM.from_env()
    except LLMUnavailable as exc:
        print(f"{exc}. Back-translation needs a model provider.")
        return 2
    cards = sorted(CARDS_DIR.rglob("*.json"))
    flags, unchecked = [], []
    for path in cards:  # one bad card is listed and skipped, so the others' paid calls are not lost
        name = path.relative_to(CARDS_DIR).as_posix()
        try:
            flags += await review(llm, name, Card.model_validate_json(path.read_text(encoding="utf-8")))
        except (LLMError, TimeoutError, ValueError, AttributeError) as exc:
            print(f"  {name}: not checked ({type(exc).__name__}: {exc})")
            unchecked.append(name)
            continue
        print(f"  {name}: checked")
    old = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(render(flags, len(cards) - len(unchecked), old, tuple(unchecked)), encoding="utf-8")
    print(f"{len(flags)} flagged, {len(unchecked)} not checked -> {REPORT.relative_to(ROOT).as_posix()}")
    return 1 if unchecked else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""The debate: an Agent Framework workflow with one executor per agent.

Hype -> Sceptic -> Verdict -> Personaliser -> (Translator-ES || Translator-AR) -> join.
Each agent makes one model call with its own timeout (never past the window budget), grounds
its text (numbers only through evidence placeholders) and, on any failure, falls back on its
own: speakers to the cached or template line; the Personaliser and each translator by leaving
their piece out, so the caller keeps the cached or template text. The workflow always completes.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from second_look.grounding import GroundingError, ground, number_words, placeholders
from second_look.llm import LLMError

PROMPTS = Path(__file__).parent / "prompts"
SPEAKERS = ("hype", "sceptic", "verdict")
LANGUAGE = {"es": "Spanish", "ar": "Arabic"}
AGENTS = (*SPEAKERS, "personaliser", *LANGUAGE)  # also the keys of a card's `source`
TEMPERATURE = {"hype": 0.7, "sceptic": 0.7, "verdict": 0.3, "personaliser": 0.3, "es": 0.3, "ar": 0.3}
MAX_TOKENS = {"hype": 80, "sceptic": 80, "verdict": 80, "personaliser": 200, "es": 800, "ar": 800}
CALL_TIMEOUT_S = 8.0
WINDOW_CAP_S = 25.0  # a 5-minute window lasts 30s of wall clock at 10x
MAX_WORDS = 14
VARIANT_WORDS = {"analyst": 25, "casual": 16}
FAILURES = (LLMError, TimeoutError, GroundingError, ValueError, KeyError, TypeError)


@dataclass
class DebateState:
    detector: str
    shown: dict[str, dict[str, str]]  # placeholder -> {lang: shown value}, the card's evidence_display
    claim: str | None  # the prediction the Verdict must make, if any, in placeholder form
    fallback: dict[str, tuple[str, str]]  # speaker -> (EN line, its source) used when the agent fails
    deadline: float  # event-loop time when the window budget runs out
    lines: dict[str, str] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)  # spelled-out numbers for human review
    raw: dict[str, str] = field(default_factory=dict)  # live English pieces in placeholder form, for the translators
    variants: dict[str, str] = field(default_factory=dict)  # persona -> live English Verdict line
    translations: dict[str, dict[str, str]] = field(default_factory=dict)  # lang -> piece -> live line


def _fit(raw: str, shown: dict[str, dict[str, str]], limit: int) -> tuple[str, str]:
    """(placeholder form, English) of `raw`, cut word by word until the English fits `limit` words."""
    text, words = ground(raw, shown, "en"), raw.split()
    while len(text.split()) > limit:
        words.pop()
        raw = " ".join(words).rstrip(".,;:") + "…"
        text = ground(raw, shown, "en")
    return raw, text


class Agent(Executor):
    """One JSON model call per run, timed out within the window budget, retried once if `accept` rejects it."""

    def __init__(self, id: str, llm, system: str, *, fail: bool = False):
        super().__init__(id=id)
        self.llm, self.system, self.fail = llm, system, fail

    async def _ask(self, state: DebateState, user: str, accept: Callable[[dict], object]):
        if self.fail:
            raise LLMError("forced failure")
        for retry in (False, True):
            remaining = state.deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("window budget spent")
            raw = await self.llm.complete(
                self.system,
                user,
                temperature=TEMPERATURE[self.id],
                max_tokens=MAX_TOKENS[self.id],
                timeout_s=min(CALL_TIMEOUT_S, remaining),
                json=True,
            )
            try:
                return accept(json.loads(raw))
            except GroundingError as exc:
                if retry or remaining <= 1:
                    raise
                user += f"\nYour last reply was rejected: {exc}. Fix that and reply again in the same JSON shape."

    async def _try(self, state: DebateState, user: str, accept: Callable[[dict], object]):
        """`_ask`, or None when the agent fails for any reason (the caller then falls back)."""
        try:
            return await self._ask(state, user, accept)
        except FAILURES:
            return None


def _evidence(state: DebateState) -> dict[str, str]:
    """Placeholder -> shown value (team name, not id), so the model reasons on values but writes keys."""
    return {f"{{{k}}}": v["en"] for k, v in sorted(state.shown.items())}


class Speaker(Agent):
    """Hype, Sceptic or Verdict: one line, having heard the speakers before it."""

    def __init__(self, role: str, llm, *, fail: bool = False):
        system = (
            (PROMPTS / "rules.md").read_text(encoding="utf-8")
            + "\n"
            + (PROMPTS / f"{role}.md").read_text(encoding="utf-8")
        )
        super().__init__(role, llm, system, fail=fail)

    @handler
    async def speak(self, state: DebateState, ctx: WorkflowContext[DebateState]) -> None:
        user = json.dumps(
            {
                "detector": state.detector,
                "evidence": _evidence(state),
                "claim": state.claim,
                "so_far": {s: state.lines[s] for s in SPEAKERS if s in state.lines},
            },
            ensure_ascii=False,
        )
        fitted = await self._try(state, user, lambda r: _fit(str(r["line"]).strip(), state.shown, MAX_WORDS))
        if fitted is None:
            state.lines[self.id], state.source[self.id] = state.fallback[self.id]
        else:
            raw, text = fitted
            state.raw[self.id], state.lines[self.id], state.source[self.id] = raw, text, "live"
            state.flags += number_words(text, "en")
        await ctx.send_message(state)


class Personaliser(Agent):
    """Rewrites the Verdict for the analyst and casual personas."""

    def __init__(self, llm, *, fail: bool = False):
        super().__init__("personaliser", llm, (PROMPTS / "personaliser.md").read_text(encoding="utf-8"), fail=fail)

    @staticmethod
    def _variant(state: DebateState, raw: str, limit: int) -> tuple[str, str]:
        """The model's line fitted to its limit. On a prediction card the claim is appended verbatim as an extra
        sentence, because this is the Verdict viewers see and the model's wording may drop the prediction."""
        if not state.claim:
            return _fit(raw, state.shown, limit)
        words = len(ground(raw, state.shown, "en").split())
        if words > limit:  # a cut would land right before the claim; retry told why, else fall back
            raise GroundingError(f"a line is {words} words once filled in; keep each within its max_words")
        raw = f"{raw} {state.claim}"
        return raw, ground(raw, state.shown, "en")

    @handler
    async def personalise(self, state: DebateState, ctx: WorkflowContext[DebateState]) -> None:
        user = json.dumps(
            {
                "verdict": state.lines["verdict"],
                "evidence": _evidence(state),
                "claim": state.claim,
                "max_words": VARIANT_WORDS,
            },
            ensure_ascii=False,
        )
        fitted = await self._try(
            state,
            user,
            lambda r: {p: self._variant(state, str(r[p]).strip(), limit) for p, limit in VARIANT_WORDS.items()},
        )
        if fitted is not None:  # else the caller keeps the cached or template variants
            for persona, (raw, text) in fitted.items():
                state.raw[persona], state.variants[persona] = raw, text
                state.flags += number_words(text, "en")
            state.source["personaliser"] = "live"
        await ctx.send_message(state)


class Translator(Agent):
    """Translates every live English piece into one language; any bad piece fails the whole language."""

    def __init__(self, lang: str, llm, *, fail: bool = False):
        super().__init__(lang, llm, (PROMPTS / "translator.md").read_text(encoding="utf-8"), fail=fail)

    def _accept(self, state: DebateState, reply: dict) -> dict[str, str]:
        out = {}
        for piece, raw in state.raw.items():
            translated = str(reply[piece]).strip()
            if placeholders(translated) != placeholders(raw):
                raise GroundingError(f"{piece}: placeholders changed, keep exactly {sorted(placeholders(raw))}")
            out[piece] = ground(translated, state.shown, self.id)
        return out

    @handler
    async def translate(self, state: DebateState, ctx: WorkflowContext[DebateState]) -> None:
        if state.raw:
            user = json.dumps({"language": LANGUAGE[self.id], "lines": state.raw}, ensure_ascii=False)
            translated = await self._try(state, user, lambda r: self._accept(state, r))
            if translated is not None:  # else the caller keeps the cached or template text for this language
                state.translations[self.id], state.source[self.id] = translated, "live"
        await ctx.send_message(state)


class Join(Executor):
    """Fan-in: both translators share one state, so either copy is the result."""

    @handler
    async def join(self, states: list[DebateState], ctx: WorkflowContext[Never, DebateState]) -> None:
        await ctx.yield_output(states[0])


async def run_debate(llm, state: DebateState, *, fail: frozenset[str] = frozenset()) -> DebateState:
    """Run the five agents. `fail` forces named agents to fail (the recorded failure demo)."""
    hype, sceptic, verdict = (Speaker(s, llm, fail=s in fail) for s in SPEAKERS)
    personaliser = Personaliser(llm, fail="personaliser" in fail)
    translators = [Translator(lang, llm, fail=lang in fail) for lang in LANGUAGE]
    workflow = (
        WorkflowBuilder(start_executor=hype, name="debate")
        .add_chain([hype, sceptic, verdict, personaliser])
        .add_fan_out_edges(personaliser, translators)
        .add_fan_in_edges(translators, Join(id="join"))
        .build()
    )
    result = await workflow.run(state)
    return result.get_outputs()[0]


def new_state(
    detector: str,
    shown: dict,
    claim: str | None,
    fallback: dict[str, tuple[str, str]],
    budget_s: float = WINDOW_CAP_S,
) -> DebateState:
    return DebateState(detector, shown, claim, fallback, asyncio.get_running_loop().time() + budget_s)

"""The Hype -> Sceptic -> Verdict debate: an Agent Framework workflow, one executor per agent.

Each executor makes one model call with its own timeout (never past the window budget),
grounds the line (numbers only through evidence placeholders) and, on any failure, falls
back on its own to the cached line or the template line. The workflow always completes.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from second_look.grounding import GroundingError, ground, number_words
from second_look.llm import LLMError

PROMPTS = Path(__file__).parent / "prompts"
SPEAKERS = ("hype", "sceptic", "verdict")
TEMPERATURE = {"hype": 0.7, "sceptic": 0.7, "verdict": 0.3}
CALL_TIMEOUT_S = 8.0
WINDOW_CAP_S = 25.0  # a 5-minute window lasts 30s of wall clock at 10x
MAX_WORDS = 14


@dataclass
class DebateState:
    detector: str
    evidence: dict
    shown: dict[str, dict[str, str]]  # evidence_display
    claim: str | None  # the prediction the Verdict must make, if any
    fallback: dict[str, tuple[str, str]]  # speaker -> (EN line, its source) used when the agent fails
    deadline: float  # event-loop time when the window budget runs out
    lines: dict[str, str] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)  # spelled-out numbers for human review


class Speaker(Executor):
    def __init__(self, role: str, llm, *, last: bool = False, fail: bool = False):
        super().__init__(id=role)
        self.llm, self.last, self.fail = llm, last, fail
        self.system = (
            (PROMPTS / "rules.md").read_text(encoding="utf-8")
            + "\n"
            + (PROMPTS / f"{role}.md").read_text(encoding="utf-8")
        )

    @handler
    async def speak(self, state: DebateState, ctx: WorkflowContext[DebateState, DebateState]) -> None:
        state.lines[self.id], state.source[self.id] = await self._line(state)
        await (ctx.yield_output(state) if self.last else ctx.send_message(state))

    async def _line(self, state: DebateState) -> tuple[str, str]:
        remaining = state.deadline - asyncio.get_running_loop().time()
        try:
            if self.fail:
                raise LLMError("forced failure")
            raw = await self.llm.complete(
                self.system,
                self._user(state),
                temperature=TEMPERATURE[self.id],
                max_tokens=80,
                timeout_s=min(CALL_TIMEOUT_S, remaining),
                json=True,
            )
            text = ground(str(json.loads(raw)["line"]).strip(), state.shown, "en")
        except (LLMError, TimeoutError, GroundingError, ValueError, KeyError, TypeError):
            return state.fallback[self.id]
        words = text.split()
        if len(words) > MAX_WORDS:
            text = " ".join(words[:MAX_WORDS]).rstrip(".,;:") + "…"
        state.flags += number_words(text, "en")
        return text, "live"

    def _user(self, state: DebateState) -> str:
        return json.dumps(
            {
                "detector": state.detector,
                "evidence": state.evidence,
                "placeholders": sorted(state.shown),
                "claim": state.claim,
                "so_far": {s: state.lines[s] for s in SPEAKERS if s in state.lines},
            },
            ensure_ascii=False,
        )


async def run_debate(llm, state: DebateState, *, fail: frozenset[str] = frozenset()) -> DebateState:
    """Run Hype -> Sceptic -> Verdict. `fail` forces named agents to fail (the recorded failure demo)."""
    hype, sceptic, verdict = (Speaker(s, llm, last=s == "verdict", fail=s in fail) for s in SPEAKERS)
    workflow = WorkflowBuilder(start_executor=hype, name="debate").add_chain([hype, sceptic, verdict]).build()
    result = await workflow.run(state)
    return result.get_outputs()[0]


def new_state(
    detector: str,
    evidence: dict,
    shown: dict,
    claim: str | None,
    fallback: dict[str, tuple[str, str]],
    budget_s: float = WINDOW_CAP_S,
) -> DebateState:
    return DebateState(detector, evidence, shown, claim, fallback, asyncio.get_running_loop().time() + budget_s)

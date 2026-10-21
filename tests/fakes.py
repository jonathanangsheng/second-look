"""Test doubles. Tests never call a real model."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class LLMCall:
    system: str
    user: str
    temperature: float
    max_tokens: int
    timeout_s: float
    json: bool


@dataclass
class FakeLLM:
    """Scripted stand-in for second_look.llm.LLM (same `complete` signature).

    Queue replies with `reply(...)`; queue a timeout with `timeout()`. Each call pops one
    scripted result in order, records the call, and raises TimeoutError for a queued
    timeout (the real LLMTimeout must subclass TimeoutError).
    """

    script: deque[str | BaseException] = field(default_factory=deque)
    calls: list[LLMCall] = field(default_factory=list)

    def reply(self, text: str) -> FakeLLM:
        self.script.append(text)
        return self

    def timeout(self) -> FakeLLM:
        self.script.append(TimeoutError("fake timeout"))
        return self

    async def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        json: bool = False,
    ) -> str:
        self.calls.append(LLMCall(system, user, temperature, max_tokens, timeout_s, json))
        if not self.script:
            raise AssertionError(f"FakeLLM got unscripted call #{len(self.calls)}")
        result = self.script.popleft()
        if isinstance(result, BaseException):
            raise result
        return result

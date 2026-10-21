"""Provider ordering, fallback, rate limits and time budget of second_look.llm (no network)."""

import asyncio
from types import SimpleNamespace

import httpx2 as httpx  # openai 3.x builds its errors on httpx2
import openai
import pytest

from second_look.config import Settings
from second_look.llm import LLM, LLMRateLimited, LLMTimeout, LLMUnavailable, Provider


def _status_error(cls, status):
    request = httpx.Request("POST", "https://example.invalid/chat/completions")
    return cls(f"HTTP {status}", response=httpx.Response(status, request=request), body=None)


class FakeClient:
    """Stands in for AsyncOpenAI: `chat.completions.create` returns or raises scripted results."""

    def __init__(self, result=None, *, delay=0.0):
        self.result = result
        self.delay = delay
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, BaseException):
            raise self.result
        message = SimpleNamespace(content=self.result)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _run(llm, **overrides):
    kwargs = {"temperature": 0.3, "max_tokens": 20, "timeout_s": 2.0, **overrides}
    return asyncio.run(llm.complete_detailed("sys", "user", **kwargs))


def test_first_configured_provider_answers_and_later_ones_are_not_called():
    first, second = FakeClient("OK"), FakeClient("unused")
    result = _run(LLM([Provider("foundry", "m1", first), Provider("github", "m2", second)]))
    assert (result.text, result.provider, result.model) == ("OK", "foundry", "m1")
    assert second.calls == []


@pytest.mark.parametrize(
    "error",
    [
        _status_error(openai.RateLimitError, 429),
        _status_error(openai.AuthenticationError, 401),
        _status_error(openai.InternalServerError, 503),
        openai.APIConnectionError(request=httpx.Request("POST", "https://example.invalid")),
    ],
    ids=["429", "401", "503", "connection"],
)
def test_failing_provider_falls_back_to_the_next(error):
    first, second = FakeClient(error), FakeClient("OK")
    result = _run(LLM([Provider("foundry", "m1", first), Provider("github", "m2", second)]))
    assert result.provider == "github"
    assert len(first.calls) == len(second.calls) == 1


class PlainTextClient(FakeClient):
    """Mimics an endpoint that answers 200 text/plain: the SDK hands back a bare string."""

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return "OK"


def test_non_completion_reply_counts_as_failure_and_falls_back():
    stub, real = PlainTextClient(), FakeClient("banana")
    result = _run(LLM([Provider("github", "m1", stub), Provider("foundry", "m2", real)]))
    assert (result.text, result.provider) == ("banana", "foundry")


def test_only_non_completion_replies_raise_unavailable():
    with pytest.raises(LLMUnavailable, match="not a chat completion"):
        _run(LLM([Provider("github", "m", PlainTextClient())]))


def test_every_provider_rate_limited_raises_rate_limited():
    providers = [Provider(n, "m", FakeClient(_status_error(openai.RateLimitError, 429))) for n in ("foundry", "github")]
    with pytest.raises(LLMRateLimited, match="foundry, github"):
        _run(LLM(providers))


def test_mixed_failures_raise_unavailable_naming_each_provider():
    providers = [
        Provider("foundry", "m", FakeClient(_status_error(openai.AuthenticationError, 401))),
        Provider("github", "m", FakeClient(_status_error(openai.RateLimitError, 429))),
    ]
    with pytest.raises(LLMUnavailable, match=r"foundry: HTTP 401.*github: 429"):
        _run(LLM(providers))


def test_slow_provider_exceeds_budget_and_raises_timeout():
    llm = LLM([Provider("github", "m", FakeClient("late", delay=1.0))])
    with pytest.raises(LLMTimeout) as info:
        _run(llm, timeout_s=0.05)
    assert isinstance(info.value, TimeoutError)  # FakeLLM and executors rely on this


def test_zero_budget_raises_timeout_without_calling():
    client = FakeClient("OK")
    with pytest.raises(LLMTimeout):
        _run(LLM([Provider("github", "m", client)]), timeout_s=0)
    assert client.calls == []


def test_json_mode_requests_a_json_object():
    client = FakeClient('{"line": "x"}')
    _run(LLM([Provider("github", "m", client)]), json=True)
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_from_env_keeps_order_and_skips_unconfigured(monkeypatch):
    for key in (
        "FOUNDRY_OPENAI_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT",
        "FOUNDRY_API_KEY",
        "FOUNDRY_SERVERLESS_ENDPOINT",
        "FOUNDRY_SERVERLESS_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "foundry,github")
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", "test-token")
    llm = LLM.from_env(Settings.from_env(dotenv=False))
    assert [p.name for p in llm.providers] == ["github"]


def test_from_env_with_nothing_configured_raises_unavailable(monkeypatch):
    for key in (
        "FOUNDRY_OPENAI_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT",
        "GITHUB_MODELS_TOKEN",
        "FOUNDRY_SERVERLESS_ENDPOINT",
        "FOUNDRY_SERVERLESS_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(LLMUnavailable):
        LLM.from_env(Settings.from_env(dotenv=False))


def test_unknown_provider_name_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "foundry,openrouter")
    with pytest.raises(ValueError, match="openrouter"):
        Settings.from_env(dotenv=False)

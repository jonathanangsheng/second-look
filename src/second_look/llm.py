"""One chat-completion client over an ordered list of OpenAI-compatible providers.

Providers are tried in `LLM_PROVIDER` order. A rate limit (HTTP 429), another HTTP
error or a connection error moves on to the next provider; the whole call, across providers, must finish
within `timeout_s` or it raises LLMTimeout. Callers (agent executors) own the
per-piece fallback to cached or template text.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import openai
from openai import AsyncOpenAI

from second_look.config import FOUNDRY_TOKEN_SCOPE, GITHUB_MODELS_ENDPOINT, ProviderName, Settings


class LLMError(RuntimeError):
    """Base class for model-client failures."""


class LLMTimeout(LLMError, TimeoutError):
    """The call did not finish within its time budget."""


class LLMRateLimited(LLMError):
    """Every provider answered HTTP 429. Card builds stop cleanly on this."""


class LLMUnavailable(LLMError):
    """No provider is configured, or every provider failed for another reason."""


class _ChatClient(Protocol):
    chat: Any


@dataclass(frozen=True)
class Provider:
    name: ProviderName
    model: str
    client: _ChatClient


@dataclass(frozen=True)
class Completion:
    text: str
    provider: ProviderName
    model: str
    latency_ms: int


class LLM:
    def __init__(self, providers: list[Provider]):
        if not providers:
            raise LLMUnavailable("no LLM provider configured; see .env.example")
        self.providers = providers

    @classmethod
    def from_env(cls, settings: Settings | None = None) -> LLM:
        settings = settings or Settings.from_env()
        return cls([p for name in settings.llm_provider if (p := build_provider(name, settings))])

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
        result = await self.complete_detailed(
            system, user, temperature=temperature, max_tokens=max_tokens, timeout_s=timeout_s, json=json
        )
        return result.text

    async def complete_detailed(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        json: bool = False,
    ) -> Completion:
        if timeout_s <= 0:
            raise LLMTimeout("no time budget left")
        try:
            async with asyncio.timeout(timeout_s):
                return await self._try_providers(system, user, temperature, max_tokens, json)
        except TimeoutError as exc:
            if isinstance(exc, LLMTimeout):
                raise
            raise LLMTimeout(f"no reply within {timeout_s:.1f}s") from exc

    async def _try_providers(
        self, system: str, user: str, temperature: float, max_tokens: int, json: bool
    ) -> Completion:
        rate_limited: list[str] = []
        failed: list[str] = []
        for provider in self.providers:
            kwargs: dict[str, Any] = {
                "model": provider.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json:
                kwargs["response_format"] = {"type": "json_object"}
            started = time.perf_counter()
            try:
                response = await provider.client.chat.completions.create(**kwargs)
            except openai.RateLimitError:
                rate_limited.append(provider.name)
                continue
            except openai.APIStatusError as exc:  # auth, missing deployment, 5xx: try the next provider
                failed.append(f"{provider.name}: HTTP {exc.status_code}")
                continue
            except openai.APIConnectionError as exc:
                failed.append(f"{provider.name}: {type(exc).__name__}")
                continue
            choices = getattr(response, "choices", None)
            if not choices:  # e.g. a stub endpoint answering 200 text/plain to everything
                failed.append(f"{provider.name}: not a chat completion ({type(response).__name__})")
                continue
            text = (choices[0].message.content or "").strip()
            return Completion(
                text=text,
                provider=provider.name,
                model=provider.model,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
        if rate_limited and not failed:
            raise LLMRateLimited(f"rate limited by: {', '.join(rate_limited)}")
        raise LLMUnavailable("all providers failed: " + "; ".join(failed + [f"{n}: 429" for n in rate_limited]))


def build_provider(name: ProviderName, settings: Settings) -> Provider | None:
    """The configured provider for `name`, or None when its settings are missing."""
    if name == "github":
        if not settings.github_models_token:
            return None
        client = AsyncOpenAI(base_url=GITHUB_MODELS_ENDPOINT, api_key=settings.github_models_token, max_retries=0)
        return Provider(name, settings.github_models_model, client)
    if name == "foundry":
        if not (settings.foundry_endpoint and settings.foundry_deployment):
            return None
        api_key = settings.foundry_api_key or _entra_token_provider()
        client = AsyncOpenAI(base_url=settings.foundry_endpoint, api_key=api_key, max_retries=0)
        return Provider(name, settings.foundry_deployment, client)
    if name == "foundry_serverless":
        if not (settings.foundry_serverless_endpoint and settings.foundry_serverless_model):
            return None
        api_key = settings.foundry_serverless_api_key or _entra_token_provider()
        client = AsyncOpenAI(base_url=settings.foundry_serverless_endpoint, api_key=api_key, max_retries=0)
        return Provider(name, settings.foundry_serverless_model, client)
    raise ValueError(f"unknown provider {name!r}")


def _entra_token_provider():
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(DefaultAzureCredential(), FOUNDRY_TOKEN_SCOPE)

"""Repo paths and runtime settings, read from the environment (and `.env` if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

ProviderName = Literal["foundry", "foundry_serverless", "github"]
PROVIDER_NAMES: tuple[ProviderName, ...] = ("foundry", "foundry_serverless", "github")

# Repo paths: code lives in src/second_look/, runtime data at the repo root.
ROOT = Path(__file__).resolve().parents[2]
PROFILES_FILE = ROOT / "profiles" / "teams.toml"
SEEDS_DIR = ROOT / "data" / "seeds"
CARDS_DIR = ROOT / "cards"
WEB_DIST = ROOT / "web" / "dist"

GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference"

# Detectors run at every WINDOW_MINUTES boundary over all events before it.
WINDOW_MINUTES = 5
VQ_MIN_SHOTS = 8  # volume_quality: at least this many shots...
VQ_MAX_XG_PER_SHOT = 0.08  # ...averaging under this xG
SX_WINDOW_MINUTES = 30  # scoreline_xg: rolling window for both teams' xG
SX_XG_GAP = 1.0  # trailer's rolling xG must beat the leader's by this much
DEDUP_SEVERITY_RISE = 0.25  # a (team, detector) pair resurfaces only on this severity rise...
DEDUP_MINUTES = 15  # ...or after this many match minutes
FOUNDRY_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _provider_order(raw: str | None) -> tuple[ProviderName, ...]:
    names = [n.strip() for n in (raw or "foundry,github").split(",") if n.strip()]
    unknown = [n for n in names if n not in PROVIDER_NAMES]
    if unknown:
        raise ValueError(f"LLM_PROVIDER has unknown provider(s) {unknown}; allowed: {list(PROVIDER_NAMES)}")
    return tuple(names)  # type: ignore[return-value]


@dataclass(frozen=True)
class Settings:
    mode: Literal["replay", "live"] = "replay"
    llm_provider: tuple[ProviderName, ...] = ("foundry", "github")

    # Microsoft Foundry, OpenAI-compatible v1 endpoint, e.g. https://<resource>.openai.azure.com/openai/v1/
    foundry_endpoint: str | None = None
    foundry_deployment: str | None = None
    foundry_api_key: str | None = None  # optional; Entra ID (DefaultAzureCredential) when unset

    # Foundry serverless model (e.g. Phi or Mistral), only once its quota exists.
    foundry_serverless_endpoint: str | None = None
    foundry_serverless_model: str | None = None
    foundry_serverless_api_key: str | None = None

    # GitHub Models (dev and fallback).
    github_models_token: str | None = field(default=None, repr=False)
    github_models_model: str = "openai/gpt-4.1-mini"

    @classmethod
    def from_env(cls, *, dotenv: bool = True) -> Settings:
        if dotenv:
            load_dotenv(override=False)
        mode = _env("MODE") or "replay"
        if mode not in ("replay", "live"):
            raise ValueError(f"MODE must be 'replay' or 'live', got {mode!r}")
        return cls(
            mode=mode,  # type: ignore[arg-type]
            llm_provider=_provider_order(_env("LLM_PROVIDER")),
            foundry_endpoint=_env("FOUNDRY_OPENAI_ENDPOINT"),
            foundry_deployment=_env("FOUNDRY_MODEL_DEPLOYMENT"),
            foundry_api_key=_env("FOUNDRY_API_KEY"),
            foundry_serverless_endpoint=_env("FOUNDRY_SERVERLESS_ENDPOINT"),
            foundry_serverless_model=_env("FOUNDRY_SERVERLESS_MODEL"),
            foundry_serverless_api_key=_env("FOUNDRY_SERVERLESS_API_KEY"),
            github_models_token=_env("GITHUB_MODELS_TOKEN"),
            github_models_model=_env("GITHUB_MODELS_MODEL") or "openai/gpt-4.1-mini",
        )

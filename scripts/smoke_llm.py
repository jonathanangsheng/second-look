"""Check each configured model provider answers. Makes one tiny real call per provider.

Usage: uv run python scripts/smoke_llm.py
Exit code 0 when every configured provider replies OK, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import sys

from second_look.config import Settings
from second_look.llm import LLM, LLMError, build_provider


async def main() -> int:
    settings = Settings.from_env()
    print(f"LLM_PROVIDER order: {', '.join(settings.llm_provider)}")
    failures = 0
    checked = 0
    for name in settings.llm_provider:
        provider = build_provider(name, settings)
        if provider is None:
            print(f"  {name:<19} SKIPPED (not configured)")
            continue
        checked += 1
        try:
            result = await LLM([provider]).complete_detailed(
                "You are a health check.", "Reply with OK", temperature=0, max_tokens=5, timeout_s=20
            )
        except LLMError as exc:
            failures += 1
            print(f"  {name:<19} FAIL    {type(exc).__name__}: {exc}")
            continue
        ok = result.text.strip().upper().startswith("OK")
        failures += 0 if ok else 1
        status = "OK  " if ok else "FAIL"
        print(f"  {name:<19} {status}    model={result.model} latency={result.latency_ms}ms reply={result.text!r}")
    if checked == 0:
        print("No provider configured. Copy .env.example to .env and fill in at least one provider.")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Build overlay cards into cards/<seed>/<mode>/.

  uv run second-look-cards                                     # template cards, every seed
  uv run second-look-cards --source live --seed demo
  uv run second-look-cards --source live --seed demo --mode fail-sceptic

Template: existing cards are kept unless --force (which rebuilds the seed from scratch).
Live (needs a model provider in .env): debate cards whose agent lines are already live are
skipped, so a rerun resumes; --windows rebuilds chosen windows; a rate limit stops the run
cleanly without writing a half-fallback card. Record `normal` before `fail-sceptic`: the
failure demo falls back to the normal card.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time

from second_look.agents import AGENTS
from second_look.config import CARDS_DIR, ROOT
from second_look.contracts import card_path
from second_look.llm import LLM, LLMRateLimited, LLMUnavailable
from second_look.pipeline import live_debate_card, read_cards, template_cards, write_cards
from second_look.sim import SEEDS

FLAGS_FILE = ROOT / "qa" / "grounding_flags.md"


class RateLimitWatch:
    """Passes calls through; remembers whether any hit a rate limit (agents swallow errors)."""

    def __init__(self, llm: LLM):
        self.llm, self.limited = llm, False

    async def complete(self, *args, **kwargs) -> str:
        try:
            return await self.llm.complete(*args, **kwargs)
        except LLMRateLimited:
            self.limited = True
            raise


async def build_live(seed: str, mode: str, windows: set[int] | None, force: bool, llm: RateLimitWatch) -> int:
    fail = frozenset({"sceptic"}) if mode == "fail-sceptic" else frozenset()
    existing_cards = read_cards(seed, mode)
    normal_cards = existing_cards if mode == "normal" else read_cards(seed, "normal")
    latencies: list[float] = []
    for card in template_cards(seed):
        if windows and card.window not in windows:
            continue
        if card.kind != "debate":  # outcome cards are template text; fail-sceptic merges over normal
            if mode == "normal":
                write_cards([card], seed, mode)  # keeps an existing file
            continue
        existing = existing_cards.get((card.window, card.kind))
        if existing and not force and all(existing.source.get(s) == "live" for s in AGENTS if s not in fail):
            continue
        cached = normal_cards.get((card.window, card.kind))
        started = time.perf_counter()
        live, flags = await live_debate_card(card, llm, cached, fail)
        if llm.limited:
            print(f"rate limited at window {card.window}; nothing written for it. Resume later with the same command.")
            return 1
        latencies.append(time.perf_counter() - started)
        path = card_path(CARDS_DIR, seed, mode, card.window, card.kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(live.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(
            f"  {path.relative_to(ROOT).as_posix()}  {latencies[-1]:.1f}s  "
            + " ".join(f"{s}={live.source[s]}" for s in AGENTS)
        )
        if flags:
            FLAGS_FILE.parent.mkdir(exist_ok=True)
            with FLAGS_FILE.open("a", encoding="utf-8") as f:
                f.write(f"- {seed}/{mode}/{card.window}: {', '.join(flags)}\n")
    if latencies:
        p90 = statistics.quantiles(latencies, n=10)[-1] if len(latencies) > 1 else latencies[0]
        print(f"{seed}/{mode}: {len(latencies)} debates, p50 {statistics.median(latencies):.1f}s, p90 {p90:.1f}s")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="second-look-cards", description=__doc__.splitlines()[0])
    ap.add_argument("--seed", choices=sorted(SEEDS), action="append", help="repeatable; default: every seed")
    ap.add_argument("--source", choices=("template", "live"), default="template")
    ap.add_argument("--mode", choices=("normal", "fail-sceptic"), default="normal", help="live only")
    ap.add_argument("--windows", help="live only: comma-separated window numbers to rebuild, e.g. 6,11")
    ap.add_argument(
        "--force", action="store_true", help="template: delete cached cards first; live: rebuild live cards too"
    )
    args = ap.parse_args()
    seeds = args.seed or sorted(SEEDS)
    if args.source == "template":
        for seed in seeds:
            cards = template_cards(seed)
            written = write_cards(cards, seed, force=args.force)
            print(f"{seed}: {len(cards)} cards, {written} written to {CARDS_DIR / seed / 'normal'}")
        return 0
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):  # traces of each agent call to an OTLP collector
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers(service_name="second-look")
    try:
        llm = RateLimitWatch(LLM.from_env())
    except LLMUnavailable as exc:
        print(f"{exc}. Live cards need a model provider; template cards need none.")
        return 2
    windows = {int(w) for w in args.windows.split(",")} if args.windows else None

    async def build_all() -> int:  # one event loop for every seed: the model client's connections belong to it
        for seed in seeds:
            if await build_live(seed, args.mode, windows, args.force, llm):
                return 1
        return 0

    return asyncio.run(build_all())


if __name__ == "__main__":
    sys.exit(main())

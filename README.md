# Second Look

An AI sceptic for football. The scoreboard says one thing; Second Look checks whether the stat on screen is telling the whole story.

Deterministic detectors find where a headline number misleads (lots of shots but little quality, a scoreline the chances don't support). Three agents then argue about it on a broadcast-style overlay: **Hype** reads the stat at face value, **Sceptic** rebuts it with the deeper number, and **Verdict** settles it, sometimes with a prediction that the match later proves right or wrong. Every number an agent says is checked against the evidence.

It runs on a replayed synthetic match, with analyst and casual views in English, Spanish and Arabic.

## Quickstart: replay (no credentials)

Needs [uv](https://docs.astral.sh/uv/) and Node 20.19+ or 22.12+ (Vite 8).

```bash
uv sync
npm --prefix web ci
npm --prefix web run build
uv run uvicorn second_look.api:app --port 8000
```

Open http://localhost:8000. The page opens on the first debate; the chips at the top jump to each key moment.

For UI work, run the API as above and `npm --prefix web run dev` (http://localhost:5173, proxies `/api`).

## Live agents

The committed cards in `cards/` are deterministic template text. To have the agents write them:

1. Copy `.env.example` to `.env` and fill in a model provider (Microsoft Foundry recommended).
2. Check the provider answers: `uv run python scripts/smoke_llm.py`
3. Build live cards, then the recorded failure demo:

```bash
uv run second-look-cards --source live --seed demo
uv run second-look-cards --source live --seed demo --mode fail-sceptic
```

Reruns resume where they stopped. Template cards need no provider: `uv run second-look-cards`.

## Layout

```
src/second_look/   Python package
  sim.py             seeded match simulator (CLI: second-look-sim)
  stats.py           per-team aggregates at each 5-minute boundary
  detectors.py       volume-vs-quality and scoreline-vs-xG detectors, dedup and window pick
  ledger.py          predictions: fulfilled by a goal or expired at the deadline
  templates.py       deterministic EN/ES/AR card text
  agents.py          Hype -> Sceptic -> Verdict workflow (Microsoft Agent Framework)
  grounding.py       numbers only through evidence placeholders
  llm.py             model client with ordered provider fallback
  pipeline.py        cards from events, card cache read/write
  build_cards.py     card builder (CLI: second-look-cards)
  api.py             replay API and the built UI
  contracts.py       shared data models (mirrored in web/src/contracts.ts)
  config.py          paths and settings
  prompts/           agent prompts
web/               React + Vite replay UI (components/, usePlayback.ts)
profiles/          fictional team profiles
data/seeds/        committed synthetic matches
cards/             committed overlay cards
tests/             pytest suite (no test calls a real model)
scripts/           developer checks
```

The match data format is documented in [SCHEMA.md](SCHEMA.md).

## Tests

```bash
uv run pytest -q
uv run ruff check .
npm --prefix web run build
```

## Data

Fictional teams inspired by public playing-style analysis. Not affiliated with or endorsed by the Premier League or any club. All match events are synthetic; no real match data is used.

## Licence

MIT. See [LICENSE](LICENSE).

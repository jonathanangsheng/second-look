# Second Look

An AI sceptic for football: deterministic detectors find where a headline stat misleads, and an Agent Framework workflow (Hype → Sceptic → Verdict → Personaliser → Translators) argues about it as a broadcast-style overlay on a replayed synthetic match.

## Where the plan lives

- Backlog: private repo `jonathanangsheng/second-look-planning`, issues #1–#10. Each issue ends with a "Review decisions" section; those decisions override anything older in the same issue.
- Full spec and review ledgers: `.planning/specs/second-look-v1.md` (local only, gitignored). Read the relevant issue section and its Eng/Design Review decisions before starting work.

## Stack and commands

- Python 3.12 via `uv`. Never call `python` directly (it is not on PATH here).
  - `uv sync` — install
  - `uv run pytest -q` — all tests (must exit 0 before any commit)
  - `uv run second-look-sim --help` — simulator CLI (from planning #3)
- Web: React 19 + Vite + TypeScript in `web/` (`npm install`, `npm run dev` with the API running, `npm run build`).
- API: `uv run uvicorn second_look.api:app --port 8000` serves `/api/*` and, once built, `web/dist` at `/`.
- Docker: `docker compose up` serves replay mode on http://localhost:8000 with no `.env`.

## Layout (11 modules, do not add more without a reason)

```
second_look/  config, llm, sim, stats, detectors, ledger, agents, grounding, templates, pipeline, api
second_look/contracts.py   Pydantic models: Event, Contradiction, Prediction, Card (source of truth)
second_look/prompts/       agent prompts
web/src/contracts.ts       TypeScript mirror of contracts.py (keep in sync)
tests/fixtures/            sample cards and events that match the contracts
tests/fakes.py             FakeLLM for every agent test (tests never call a real model)
profiles/  data/seeds/  cards/  scripts/
```

## Rules (hard)

1. **Banned terms.** No tracked file, commit message, code comment, prompt, card or UI string may contain any term listed in the gitignored `.denylist.local`. `tests/test_repo_lint.py` and the pre-commit hook enforce it. If the file is missing, ask the owner; never guess the terms and never write them into a tracked file.
2. **Contracts first.** Change `second_look/contracts.py`, `web/src/contracts.ts` and the fixtures together, in one commit.
3. **Numbers in agent text come only from placeholders** filled from evidence; the grounding check rejects any digit not in evidence.
4. **No emoji** in UI copy or card text. No coloured left-border stripes on cards.
5. **Fictional teams and players only.** Real club names never appear in data, UI or cards.
6. **Tests never use a real model.** Use `tests/fakes.FakeLLM`. Real calls only in `scripts/`.
7. **Secrets** live in `.env` (gitignored). Never print or commit a token.

## Reporting work

- Any change to a test, threshold, timeout or validator goes on its own line in your summary, with the reason, before other results.
- Name every command you ran and its observed result (exit code, pass/fail counts). Don't report commands you did not run, and never silence stderr in a cited command.
- Say what you verified, what you reused and what you could not check.

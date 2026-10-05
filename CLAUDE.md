# AiVisibility

Measurement engine for how AI assistants mention brands (fintech pilot: Stripe, Paddle).
Docs, README and weekly specs are in Ukrainian; code, comments, docstrings and this file are in English.

## Commands
- Setup: `uv sync`
- Tests: `uv run pytest` (offline, no API keys needed)
- Lint: `uv run ruff check .`
- Pipeline scripts live in `scripts/` (one per step, see `README.md` for the order).

## Layout
- `aivisibility/` package: `analysis/` (bootstrap, convergence, adaptive sampling, mentions), `common/` (config, db, schemas), `discovery/`, `prober/`, `query_generator/`
- `docs/weeks/weekN.md` weekly specs, `docs/ai_visibility_fintech_plan.md` the 8-week plan, `docs/sdlc.md` the workflow.

## Rules
- NEVER run `scripts/run_prober.py` (or anything that calls Claude/OpenAI) without the user's explicit confirmation - it costs money. Use `--dry-run` first; pass `--max-budget-usd` on real runs.
- Tests must never hit real APIs; mock probers. Statistical tests must use a fixed `seed`.
- Follow `docs/sdlc.md` for branches, commits and the definition of done.

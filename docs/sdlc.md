# SDLC

Lightweight, solo-project workflow. One cycle = one week of `docs/ai_visibility_fintech_plan.md`.

## Cycle
1. **Plan** - write `docs/weeks/weekN.md` (goal, day-by-day tasks, risks) and a Definition of Done.
2. **Branch** - `week-N/<topic>` off `master`; `master` stays green.
3. **Build** - code in `aivisibility/`. A throwaway script becomes a tested module once other code depends on it.
4. **Test** - `uv run pytest`. Seeded, deterministic, offline; probers are mocked.
5. **Gate** - `uv run ruff check .` and `uv run pytest` locally (pre-commit) and in CI on every PR.
6. **Review** - self-review the PR diff, then squash-merge to `master`.
7. **Release** - tag `weekN-done`; fill in "Final result" and open questions in `weekN.md`.
8. **Retro** - update the plan's cut-list and risks.

## Conventions
- Commit messages: `weekN: <verb> <what>` (e.g. `week5: add adaptive sampling policy`).
- Docs in Ukrainian; code, comments and docstrings in English.
- Secrets only in `.env` (never committed); CI holds no API keys.
- Real API runs need explicit go-ahead: `run_prober.py --dry-run` first, then `--max-budget-usd`.

## Definition of Done (every week)
- [ ] Code merged via PR, CI green
- [ ] Tests for new statistical/logic code (seeded)
- [ ] `weekN.md` updated with results and open questions
- [ ] README/CLAUDE.md updated if commands or layout changed
- [ ] Tag `weekN-done` pushed

## Open decisions
- DB policy: `data/db/aivisibility.sqlite3` is currently tracked in git. Recommended: gitignore it and commit a small fixture for tests.
- Reproducibility record per run (seed, git SHA, model IDs, temperature, prompt hash) is not yet stored in the DB.

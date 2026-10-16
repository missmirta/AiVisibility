"""Run the pairwise brand comparisons (week 7) through each engine and store them.
Run: python scripts/run_pairwise.py [--dry-run] [--max-budget-usd 2.0] [--engine openai] [--limit 10]

--dry-run          print the number of calls and make zero API calls.
--max-budget-usd   stop once the accumulated cost reaches this cap.
--engine           only this engine (claude | openai); default both.
--limit            only the first N comparisons per engine (use for a cheap pilot).
"""

import argparse
import asyncio
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common import db
from aivisibility.perception.pairs import build_comparisons
from aivisibility.perception.parse import parse_choice
from aivisibility.prober import claude_prober, openai_prober

PROBERS = {"claude": claude_prober, "openai": openai_prober}
SHUFFLE_SEED = 42


async def main(
    dry_run: bool,
    max_budget_usd: float | None,
    engine: str | None,
    limit: int | None,
    probers: dict | None = None,
) -> None:
    probers = {k: v for k, v in (probers or PROBERS).items() if engine in (None, k)}
    comparisons = build_comparisons()
    # Shuffle so a --limit pilot and a budget stop both cover all pairs/attributes evenly.
    random.Random(SHUFFLE_SEED).shuffle(comparisons)
    if limit is not None:
        comparisons = comparisons[:limit]

    if dry_run:
        print(
            f"[dry-run] would send {len(comparisons) * len(probers)} requests "
            f"({len(comparisons)} comparisons x {list(probers)}). No API calls made."
        )
        return

    db.init_db()
    run_id = db.create_pairwise_run(notes=f"engines={list(probers)} n={len(comparisons)}")
    print(f"Pairwise run #{run_id}: {len(comparisons)} comparisons x {len(probers)} engine(s).")

    total_cost = 0.0
    invalid = 0
    for name, prober in probers.items():
        engine_cost = 0.0
        for c in comparisons:
            if max_budget_usd is not None and total_cost + engine_cost >= max_budget_usd:
                print(f"Budget cap ${max_budget_usd:.2f} reached - stopping {name} early.")
                break
            result = await prober.probe(c.prompt)
            choice = parse_choice(result.text) if not result.error else None
            db.insert_pairwise_response(
                run_id, name, result.model, c, result.text, choice,
                c.winner(choice), result.cost_usd, result.latency_ms, result.error,
            )
            engine_cost += result.cost_usd or 0.0
            invalid += choice is None
        print(f"  {name} subtotal: ~${engine_cost:.4f}")
        total_cost += engine_cost
    print(f"\nRun #{run_id} done: {invalid} unparsed/error answers, total cost ~${total_cost:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-budget-usd", type=float, default=None)
    parser.add_argument("--engine", choices=list(PROBERS), default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.max_budget_usd, args.engine, args.limit))

"""Run every stored query through each configured engine and store the
results. Safe to re-run repeatedly (e.g. daily via cron/Task Scheduler) —
each run gets its own run_id, no dedup needed.
Run: python scripts/run_prober.py [--dry-run] [--max-budget-usd 5.0] [--from-query-id 25] [--engine openai]

--dry-run          print what would be probed and make zero API calls.
--max-budget-usd   stop the run once the accumulated cost reaches this cap.
--from-query-id   probe only queries with this id or higher (e.g. just the newly added ones).
--engine           probe only this engine (default: all).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common import db
from aivisibility.prober import claude_prober, openai_prober

PROBERS = [claude_prober, openai_prober]


async def main(
    dry_run: bool,
    max_budget_usd: float | None,
    from_query_id: int | None = None,
    engine: str | None = None,
) -> None:
    probers = [p for p in PROBERS if engine is None or p.ENGINE == engine]
    db.init_db()
    inserted = db.load_queries_from_json()
    print(f"Loaded queries table ({inserted} new rows).")

    queries = db.get_all_queries() if from_query_id is None else db.get_queries_from(from_query_id)
    if dry_run:
        print(
            f"[dry-run] would send {len(queries) * len(probers)} requests "
            f"({len(queries)} queries x {[p.ENGINE for p in probers]}). No API calls made."
        )
        return

    run_id = db.create_run(notes=f"engines={[p.ENGINE for p in probers]}")
    print(f"Run #{run_id}: {len(queries)} queries x {len(probers)} engine(s).")

    total_cost = 0.0
    error_count = 0
    budget_hit = False

    for prober in probers:
        engine_cost = 0.0
        for q in queries:
            if max_budget_usd is not None and total_cost + engine_cost >= max_budget_usd:
                budget_hit = True
                break
            result = await prober.probe(q["text"])
            db.insert_response(
                run_id=run_id,
                query_id=q["id"],
                engine=prober.ENGINE,
                model=result.model,
                raw_text=result.text,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
                error=result.error,
            )
            engine_cost += result.cost_usd or 0.0
            status = "ERROR" if result.error else "ok"
            print(
                f"  [{prober.ENGINE}] query#{q['id']} ({q['brand']}/{q['intent']}) "
                f"{status} ~${result.cost_usd or 0:.4f} {result.latency_ms}ms"
            )
            if result.error:
                error_count += 1
        print(f"  {prober.ENGINE} subtotal: ~${engine_cost:.4f}")
        total_cost += engine_cost
        if budget_hit:
            print(f"Budget cap ${max_budget_usd:.2f} reached - stopping run early.")
            break

    status = "stopped early (budget cap)" if budget_hit else "complete"
    print(f"\nRun #{run_id} {status}: {error_count} errors, total cost ~${total_cost:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-budget-usd", type=float, default=None)
    parser.add_argument("--from-query-id", type=int, default=None, help="probe only queries with this id or higher")
    parser.add_argument("--engine", choices=[p.ENGINE for p in PROBERS], default=None, help="probe only this engine")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.max_budget_usd, args.from_query_id, args.engine))

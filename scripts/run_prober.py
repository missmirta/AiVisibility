"""Run every stored query through each configured engine and store the
results. Safe to re-run repeatedly (e.g. daily via cron/Task Scheduler) —
each run gets its own run_id, no dedup needed.
Run: python scripts/run_prober.py
"""

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common import db
from aivisibility.prober import claude_prober, openai_prober

PROBERS = [claude_prober, openai_prober]


async def main() -> None:
    db.init_db()
    inserted = db.load_queries_from_json()
    print(f"Loaded queries table ({inserted} new rows).")

    queries = db.get_all_queries()
    run_id = db.create_run(notes=f"engines={[p.ENGINE for p in PROBERS]}")
    print(f"Run #{run_id}: {len(queries)} queries x {len(PROBERS)} engine(s).")

    total_cost = 0.0
    error_count = 0

    for prober in PROBERS:
        engine_cost = 0.0
        for q in queries:
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

    print(f"\nRun #{run_id} done: {len(queries) * len(PROBERS)} responses stored, "
          f"{error_count} errors, total cost ~${total_cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())

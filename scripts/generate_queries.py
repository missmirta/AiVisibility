"""Generate the classified query set for all pilot brands from their
confirmed BrandProfile files. Run: python scripts/generate_queries.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common.config import BRANDS_DIR, PILOT_BRANDS, QUERIES_DIR, QUERIES_FILE
from aivisibility.common.schemas import BrandProfile
from aivisibility.query_generator.generator import generate_queries_for_brand


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace(".", "")


def _load_profile(name: str) -> BrandProfile:
    path = BRANDS_DIR / f"{_slug(name)}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No confirmed profile for '{name}' at {path}. "
            "Run scripts/discover_brands.py first."
        )
    return BrandProfile.model_validate_json(path.read_text(encoding="utf-8"))


async def main() -> None:
    QUERIES_DIR.mkdir(parents=True, exist_ok=True)

    all_queries = []
    total_cost = 0.0

    for brand in PILOT_BRANDS:
        name = brand["name"]
        profile = _load_profile(name)
        print(f"\n=== Query Generator: {name} ===")
        queries, cost = await generate_queries_for_brand(profile)
        total_cost += cost
        print(f"  -> {len(queries)} queries for {name}, cost ~${cost:.4f}")
        all_queries.extend(queries)

    QUERIES_FILE.write_text(
        json.dumps([q.model_dump() for q in all_queries], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nSaved {len(all_queries)} queries to {QUERIES_FILE}")
    print(f"Total cost: ~${total_cost:.4f}")

    print("\n--- Full list for manual review ---")
    for q in all_queries:
        comp = f" [{', '.join(q.mentions_competitors)}]" if q.mentions_competitors else ""
        print(f"  ({q.brand}/{q.intent}) {q.text}{comp}")


if __name__ == "__main__":
    asyncio.run(main())

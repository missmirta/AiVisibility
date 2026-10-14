"""Collect real payment-provider questions from Hacker News and Stack Overflow.

Run: uv run python scripts/collect_real_queries.py [--per-term 100] [--review-size 30] [--seed 42]

Uses only free public APIs (no keys, no Claude/OpenAI calls). Writes
data/queries/real_queries.json and data/queries/real_review.csv (a random sample
for a manual check of how many rows are off-topic).
"""

import argparse
import asyncio
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common import config
from aivisibility.representativeness.clean import clean
from aivisibility.representativeness.collect import SEARCH_TERMS, collect_hn, collect_stackexchange

OUT_FILE = config.QUERIES_DIR / "real_queries.json"
REVIEW_FILE = config.QUERIES_DIR / "real_review.csv"


async def main(per_term: int, review_size: int, seed: int) -> None:
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "aivisibility-research/0.1"}) as client:
        hn = await collect_hn(client, SEARCH_TERMS, per_term)
        se = await collect_stackexchange(client, SEARCH_TERMS, per_term)
    kept, counts = clean(hn + se)

    OUT_FILE.write_text(json.dumps([q.model_dump() for q in kept], ensure_ascii=False, indent=2), encoding="utf-8")
    sample = random.Random(seed).sample(kept, min(review_size, len(kept)))
    with REVIEW_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "source", "url", "relevant"])  # fill "relevant" with 1/0 by hand
        w.writerows([q.text, q.source, q.url, ""] for q in sample)

    print(f"raw: hackernews={len(hn)} stackoverflow={len(se)}")
    for stage, n in counts.items():
        print(f"  {stage:14s} {n}")
    print("kept by source:", dict(Counter(q.source for q in kept)))
    print(f"-> {OUT_FILE}\n-> {REVIEW_FILE} (mark the 'relevant' column by hand)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--per-term", type=int, default=100)
    p.add_argument("--review-size", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    asyncio.run(main(a.per_term, a.review_size, a.seed))

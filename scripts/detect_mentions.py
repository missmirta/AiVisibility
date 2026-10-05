"""Populate `mentions` from `responses.raw_text` for every pilot brand.

Idempotent: rerunning after a detection-logic change replaces the old rows
for each response_id instead of duplicating them.
Run: python scripts/detect_mentions.py
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.analysis.mentions import (
    METHOD,
    build_candidate_dictionary,
    detect_mentions,
    load_brand_profiles,
)
from aivisibility.common import db


def main() -> None:
    db.init_db()
    profiles = load_brand_profiles()
    candidates_by_brand = {
        brand: build_candidate_dictionary(profile) for brand, profile in profiles.items()
    }

    responses = db.get_responses_with_brand()
    total_mentions = 0
    unique_entities_by_brand: dict[str, set[str]] = defaultdict(set)
    own_brand_hits: dict[str, int] = defaultdict(int)
    own_brand_total: dict[str, int] = defaultdict(int)

    for row in responses:
        subject_brand = row["subject_brand"]
        candidates = candidates_by_brand.get(subject_brand)
        if candidates is None:
            print(f"  WARN: no brand profile for '{subject_brand}', "
                  f"skipping response#{row['response_id']}")
            continue

        text = row["raw_text"] or ""
        found = detect_mentions(text, candidates) if text else []
        db.replace_mentions_for_response(row["response_id"], found, METHOD)

        total_mentions += len(found)
        unique_entities_by_brand[subject_brand].update(found)

        if text:
            own_brand_total[subject_brand] += 1
            if subject_brand in found:
                own_brand_hits[subject_brand] += 1

    print(f"mentions: {total_mentions} rows inserted across {len(responses)} responses.\n")

    print("Unique mentioned entities per brand (out of possible candidates):")
    for brand in sorted(candidates_by_brand):
        unique_count = len(unique_entities_by_brand.get(brand, set()))
        total_candidates = len(candidates_by_brand[brand])
        print(f"  {brand}: {unique_count}/{total_candidates}")

    print("\nOwn-brand mention rate (sanity check, expecting >80%):")
    for brand in sorted(own_brand_total):
        hits = own_brand_hits[brand]
        n = own_brand_total[brand]
        rate = hits / n * 100 if n else 0.0
        print(f"  {brand}: {hits}/{n} ({rate:.0f}%)")


if __name__ == "__main__":
    main()

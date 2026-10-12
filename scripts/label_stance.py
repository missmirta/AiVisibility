"""Label stance snippets from stored answers with Claude and write the CSV
that scripts/train_classifier.py trains on.

Run: uv run python scripts/label_stance.py --dry-run
     uv run python scripts/label_stance.py --max-budget-usd 2.0
     uv run python scripts/label_stance.py --only-unlabeled --max-budget-usd 0.7

--dry-run          count snippets and estimate cost; makes zero API calls.
--max-budget-usd   REQUIRED for a real run; stops once spending reaches it.
--only-unlabeled   skip snippets already in the labels file and append the new labels to it.

Also writes a small seeded sample (stance_review.csv) for a manual spot check.
"""

import argparse
import asyncio
import csv
import math
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.labeler import BATCH_SIZE, label_snippets
from aivisibility.classifier.snippets import load_snippets
from aivisibility.common import config, db
from aivisibility.prober import claude_prober

REVIEW_SIZE = 30


def avg_claude_call_cost() -> float:
    """Mean cost of past Claude calls, as a rough per-call estimate."""
    with db.connect() as conn:
        row = conn.execute("SELECT AVG(cost_usd) AS c FROM responses WHERE engine = 'claude' AND cost_usd > 0").fetchone()
    return row["c"] or 0.0


def write_csv(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label", "brand", "response_id"])
        writer.writerows(rows)


def read_labeled(path: Path) -> tuple[list[tuple], set[tuple[str, str]]]:
    """Existing label rows and their (response_id, brand) keys."""
    if not path.exists():
        return [], set()
    with open(path, encoding="utf-8", newline="") as f:
        rows = [(r["text"], r["label"], r["brand"], r["response_id"]) for r in csv.DictReader(f)]
    return rows, {(r[3], r[2]) for r in rows}


async def main(
    dry_run: bool,
    max_budget_usd: float | None,
    seed: int,
    output: Path | None,
    overwrite: bool,
    only_unlabeled: bool = False,
) -> None:
    out_path = output or config.STANCE_LABELS_FILE
    snippets = load_snippets()
    kept_rows: list[tuple] = []
    if only_unlabeled:
        kept_rows, done = read_labeled(out_path)
        snippets = [s for s in snippets if (str(s.response_id), s.brand) not in done]
        print(f"Keeping {len(kept_rows)} existing labels; labeling only the unlabeled snippets.")
    calls = math.ceil(len(snippets) / BATCH_SIZE)
    estimate = calls * avg_claude_call_cost()
    print(f"{len(snippets)} snippets -> {calls} calls (batch {BATCH_SIZE}), estimated ~${estimate:.2f}")

    if dry_run:
        print("[dry-run] No API calls made.")
        return
    if max_budget_usd is None:
        raise SystemExit("Pass --max-budget-usd for a real run (or --dry-run).")

    if out_path.exists() and not overwrite and not only_unlabeled:
        raise SystemExit(f"{out_path} exists; pass --output NEW_FILE or --overwrite.")

    labeled, spent = await label_snippets(snippets, claude_prober.probe, max_budget_usd)
    rows = kept_rows + [(s.model_input, label, s.brand, s.response_id) for s, label in labeled]
    write_csv(out_path, rows)

    counts = {name: sum(1 for r in rows if r[1] == name) for name in config.STANCE_LABELS}
    print(f"Labeled {len(labeled)}/{len(snippets)} snippets ({len(rows)} rows in total), spent ~${spent:.4f}: {counts}")
    print(f"Wrote {out_path}")

    sample = random.Random(seed).sample(rows, min(REVIEW_SIZE, len(rows)))
    review_path = out_path.with_name(f"{out_path.stem}_review.csv")
    write_csv(review_path, sample)
    print(f"Wrote {len(sample)}-row sample for manual review: {review_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-budget-usd", type=float, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None, help="labels CSV to write (default: stance.csv)")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing output file")
    parser.add_argument("--only-unlabeled", action="store_true", help="keep existing labels, label only new snippets")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.max_budget_usd, args.seed, args.output, args.overwrite, args.only_unlabeled))

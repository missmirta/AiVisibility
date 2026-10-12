"""Write a gold-labeling sheet for hand labeling, with Claude's labels hidden.

Run: uv run python scripts/make_gold_set.py [--n 120]

Fill the `human_label` column in data/labels/gold.csv (recommended / neutral /
negative) without looking at gold_claude_key.csv, then run
scripts/evaluate_classifier.py. Never overwrites a sheet that is already filled in.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.data import load_rows, sample_gold, write_rows
from aivisibility.common import config

GOLD_FILE = config.STANCE_LABELS_FILE.with_name("gold.csv")
KEY_FILE = config.STANCE_LABELS_FILE.with_name("gold_claude_key.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if GOLD_FILE.exists() and any(r["human_label"] for r in load_rows(GOLD_FILE)):
        raise SystemExit(f"{GOLD_FILE} already has human labels; move it away to start over.")

    rows = load_rows(config.STANCE_LABELS_FILE)
    gold = sample_gold(rows, args.n, args.seed)
    sheet = [
        {"row_id": str(i), "text": r["text"], "brand": r["brand"], "response_id": r["response_id"], "human_label": ""}
        for i, r in enumerate(gold)
    ]
    key = [{"row_id": str(i), "claude_label": r["label"]} for i, r in enumerate(gold)]
    write_rows(GOLD_FILE, sheet, ["row_id", "text", "brand", "response_id", "human_label"])
    write_rows(KEY_FILE, key, ["row_id", "claude_label"])
    print(f"Wrote {len(sheet)} rows to {GOLD_FILE} (fill in human_label); Claude's labels are in {KEY_FILE}.")


if __name__ == "__main__":
    main()

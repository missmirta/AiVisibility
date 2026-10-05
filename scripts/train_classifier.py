"""Train the stance classifier from a labeled CSV and log it to MLflow.

Usage:
    uv run python scripts/train_classifier.py [--labels data/labels/stance.csv] [--promote]

The CSV has two columns: `text` (an AI answer or a snippet) and `label`
(one of config.STANCE_LABELS). No API calls are made here.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.train import latest_version, promote, train
from aivisibility.common import config


def load_labeled(path: Path) -> tuple[list[str], list[str]]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    bad = {r["label"] for r in rows} - set(config.STANCE_LABELS)
    if bad:
        raise SystemExit(f"Unknown labels in {path}: {sorted(bad)}")
    return [r["text"] for r in rows], [r["label"] for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=config.STANCE_LABELS_FILE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--C", type=float, default=1.0)
    parser.add_argument("--promote", action="store_true", help="point the production alias at the new version")
    args = parser.parse_args()

    if not args.labels.exists():
        raise SystemExit(f"No labels file at {args.labels}")

    texts, labels = load_labeled(args.labels)
    metrics = train(texts, labels, seed=args.seed, C=args.C)
    print(f"Trained on {len(texts)} rows: {metrics}")

    if args.promote:
        version = latest_version()
        promote(version)
        print(f"Alias production -> v{version}")


if __name__ == "__main__":
    main()

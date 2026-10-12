"""Labeled-data helpers: CSV loading and the human gold-set sample."""

import csv
import random
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sample_gold(rows: list[dict[str, str]], n: int, seed: int) -> list[dict[str, str]]:
    """Class-balanced sample of up to `n` rows. Small classes give everything
    they have, and the shortfall is spread over the larger ones."""
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(row)

    rng = random.Random(seed)
    picked: list[dict[str, str]] = []
    labels_left = sorted(by_label, key=lambda k: len(by_label[k]))
    remaining = n
    for i, label in enumerate(labels_left):
        quota = min(len(by_label[label]), remaining // (len(labels_left) - i))
        picked.extend(rng.sample(by_label[label], quota))
        remaining -= quota
    rng.shuffle(picked)
    return picked

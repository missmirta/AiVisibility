"""Compare competitor mention rates between two runs and print a verdict —
"NOISE" if the bootstrap CIs overlap, "POSSIBLE CHANGE" otherwise.

Run: python scripts/analyze_mentions.py [run_id_a run_id_b | --window-days N]
Without arguments, compares the two most recent runs in the database.
With --window-days N, compares the last N days against the N days before.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.analysis.report import MentionRateRow, compute_mention_rates
from aivisibility.common import db


def _fmt(row: MentionRateRow) -> str:
    half_width_pp = (row.upper - row.lower) / 2 * 100
    return f"{row.point * 100:.0f}% ± {half_width_pp:.0f}pp"


def _overlaps(a: MentionRateRow, b: MentionRateRow) -> bool:
    return a.lower <= b.upper and b.lower <= a.upper


def _by_key(rows: list[MentionRateRow]) -> dict[tuple[str, str, str], MentionRateRow]:
    return {(r.subject_brand, r.engine, r.mentioned_entity): r for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_ids", nargs="*", type=int, help="two run ids (optional)")
    parser.add_argument(
        "--window-days",
        type=int,
        help="compare the last N days with the N days before them instead of two runs",
    )
    args = parser.parse_args()

    window = args.window_days
    if window is not None:
        if window < 1 or args.run_ids:
            parser.error("--window-days must be >= 1 and cannot be combined with run ids")
        now = datetime.now(UTC)
        label_a, label_b = f"{2 * window}-{window} days ago", f"last {window} days"
        print(f"Window comparison: {label_a} (period 1) vs {label_b} (period 2)\n")
        rows_a = _by_key(compute_mention_rates(window_days=window, now=now - timedelta(days=window)))
        rows_b = _by_key(compute_mention_rates(window_days=window, now=now))
    else:
        if len(args.run_ids) == 2:
            run_a, run_b = args.run_ids
        elif not args.run_ids:
            run_ids = db.get_run_ids()
            if len(run_ids) < 2:
                print("At least 2 runs are needed for a comparison — "
                      "do one more python scripts/run_prober.py.")
                sys.exit(1)
            run_a, run_b = run_ids[-2], run_ids[-1]
        else:
            parser.error("pass exactly two run ids, or none")
        label_a, label_b = f"run#{run_a}", f"run#{run_b}"
        print(f"Comparison of run#{run_a} (period 1) vs run#{run_b} (period 2)\n")
        rows_a = _by_key(compute_mention_rates(run_a))
        rows_b = _by_key(compute_mention_rates(run_b))
    common_keys = sorted(set(rows_a) & set(rows_b))

    noise_count = 0
    change_count = 0
    for subject_brand, engine, entity in common_keys:
        if entity == subject_brand:
            continue  # own-brand rate is trivially high — see week3.md; focus on competitors

        row_a, row_b = rows_a[(subject_brand, engine, entity)], rows_b[(subject_brand, engine, entity)]
        noise = _overlaps(row_a, row_b)
        noise_count += noise
        change_count += not noise

        print(f"{subject_brand} / {engine} / {entity}: "
              f"{_fmt(row_a)} ({label_a}) vs {_fmt(row_b)} ({label_b})")
        if noise:
            print("  -> intervals overlap -> NOISE, not a trend")
        elif window is not None:
            print(f"  -> intervals do NOT overlap -> POSSIBLE CHANGE "
                  f"(N={row_a.n} vs N={row_b.n}; check whether the model was updated "
                  "at the window boundary)")
        else:
            print(f"  -> intervals do NOT overlap -> POSSIBLE CHANGE "
                  f"(caution: N={row_a.n} per group, both runs from the same day — "
                  "do not interpret as a confirmed trend)")

    print(f"\nSummary: {noise_count} pairs are noise, {change_count} pairs are a possible change.")
    if window is not None:
        return
    print(
        f"\nCaveat: run#{run_a} and run#{run_b} are same-day runs minutes apart, not "
        "truly different observation periods. This demonstrates the "
        "\"do the intervals overlap\" method, not proof of an actual change in brand "
        "visibility over time; a real longitudinal trend needs cron collection over "
        "weeks/months (out of scope for this week). With N=12 per group even "
        "non-overlapping intervals should not be read as a reliable signal."
    )


if __name__ == "__main__":
    main()

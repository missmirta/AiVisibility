"""Compare competitor mention rates between two runs and print a verdict —
"ШУМ" if the bootstrap CIs overlap, "МОЖЛИВА ЗМІНА" otherwise.

Run: python scripts/analyze_mentions.py [run_id_a] [run_id_b]
Without arguments, compares the two most recent runs in the database.
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.analysis.report import MentionRateRow, compute_mention_rates
from aivisibility.common import db


def _fmt(row: MentionRateRow) -> str:
    half_width_pp = (row.upper - row.lower) / 2 * 100
    return f"{row.point * 100:.0f}% ± {half_width_pp:.0f}пп"


def _overlaps(a: MentionRateRow, b: MentionRateRow) -> bool:
    return a.lower <= b.upper and b.lower <= a.upper


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2:
        run_a, run_b = int(args[0]), int(args[1])
    else:
        run_ids = db.get_run_ids()
        if len(run_ids) < 2:
            print("Потрібно щонайменше 2 прогони (runs) для порівняння — "
                  "виконайте ще один python scripts/run_prober.py.")
            sys.exit(1)
        run_a, run_b = run_ids[-2], run_ids[-1]

    print(f"Порівняння run#{run_a} (період 1) vs run#{run_b} (період 2)\n")

    rows_a = {(r.subject_brand, r.engine, r.mentioned_entity): r for r in compute_mention_rates(run_a)}
    rows_b = {(r.subject_brand, r.engine, r.mentioned_entity): r for r in compute_mention_rates(run_b)}
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
              f"{_fmt(row_a)} (run#{run_a}) vs {_fmt(row_b)} (run#{run_b})")
        if noise:
            print("  -> інтервали перетинаються -> ШУМ, не тренд")
        else:
            print(f"  -> інтервали НЕ перетинаються -> МОЖЛИВА ЗМІНА "
                  f"(обережно: N={row_a.n} на групу, обидва прогони того самого дня — "
                  "не варто інтерпретувати як підтверджений тренд)")

    print(f"\nПідсумок: {noise_count} пар — шум, {change_count} пар — можлива зміна.")
    print(
        "\nЗастереження: run#{a} і run#{b} — прогони того самого дня з різницею в "
        "хвилини, а не реальні різні періоди спостереження. Це демонстрація методу "
        "\"чи інтервали перетинаються\", а не доказ фактичної зміни видимості бренду "
        "в часі; реальний лонгітюдний тренд потребує cron-збору за тижні/місяці "
        "(поза скоупом цього тижня). При N=12 на групу навіть непересічні інтервали "
        "не варто інтерпретувати як надійний сигнал.".format(a=run_a, b=run_b)
    )


if __name__ == "__main__":
    main()

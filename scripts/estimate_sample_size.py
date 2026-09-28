"""Empirical minimum-n orientation per engine, from the convergence curves
(crossing point if observed, otherwise an extrapolation of the curve's
1/sqrt(n) shape — see docs/weeks/week4.md for the honesty caveats).
Run: python scripts/estimate_sample_size.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.analysis.convergence import (
    aggregate_curves_by_engine,
    estimate_min_n,
    pooled_mention_vectors,
)

TARGET_PP = 5.0


def main() -> None:
    vectors = pooled_mention_vectors()
    curves = aggregate_curves_by_engine(vectors, seed=42)

    print(f"Емпіричний орієнтир мінімального n на движок (ціль: ±{TARGET_PP:.0f} в.п.)\n")

    for engine, curve in sorted(curves.items()):
        result = estimate_min_n(engine, curve, target_pp=TARGET_PP)
        print(f"{engine}:")
        print(f"  спостережено до n={result.max_observed_n}, "
              f"ширина CI на n={result.max_observed_n} ≈ {result.width_at_max_n:.1f} в.п.")
        if result.observed_n is not None:
            print(f"  ціль ±{TARGET_PP:.0f} в.п. ДОСЯГНУТА в межах наявних даних: n={result.observed_n}")
        else:
            print(f"  ціль ±{TARGET_PP:.0f} в.п. НЕ досягнута в межах наявних даних")
            print(f"  екстраполяція (1/sqrt(n) fit): n ≈ {result.extrapolated_n} запитів на движок")
        print(f"  {result.fit_note}\n")

    print(
        "Застереження: це емпіричний орієнтир для нашого сетапу (2 бренди fintech, "
        "ці конкретні движки й запити), не універсальна формула мінімального "
        "розміру вибірки — та строга параметрична формула лишається майбутньою "
        "роботою (докладніше — docs/weeks/week4.md, докладний мастер-план)."
    )


if __name__ == "__main__":
    main()

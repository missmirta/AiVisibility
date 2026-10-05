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

    print(f"Empirical minimum-n guideline per engine (target: ±{TARGET_PP:.0f} pp)\n")

    for engine, curve in sorted(curves.items()):
        result = estimate_min_n(engine, curve, target_pp=TARGET_PP)
        print(f"{engine}:")
        print(f"  observed up to n={result.max_observed_n}, "
              f"CI width at n={result.max_observed_n} ≈ {result.width_at_max_n:.1f} pp")
        if result.observed_n is not None:
            print(f"  target ±{TARGET_PP:.0f} pp REACHED within the available data: n={result.observed_n}")
        else:
            print(f"  target ±{TARGET_PP:.0f} pp NOT reached within the available data")
            print(f"  extrapolation (1/sqrt(n) fit): n ≈ {result.extrapolated_n} queries per engine")
        print(f"  {result.fit_note}\n")

    print(
        "Caveat: this is an empirical guideline for our setup (2 fintech brands, "
        "these specific engines and queries), not a universal minimum sample size "
        "formula — a rigorous parametric formula remains future work "
        "(see docs/weeks/week4.md and the master plan)."
    )


if __name__ == "__main__":
    main()

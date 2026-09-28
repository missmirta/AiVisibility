"""Build bootstrap-CI-width-vs-n convergence curves per engine from the
data already collected in weeks 2-3 (subsampling — no new Prober calls),
print them, and save a comparison chart.
Run: python scripts/build_convergence_curves.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aivisibility.analysis.convergence import aggregate_curves_by_engine, pooled_mention_vectors
from aivisibility.common.config import REPORTS_DIR


def main() -> None:
    vectors = pooled_mention_vectors()
    pool_sizes = {engine: 0 for (_b, engine, _e) in vectors}
    for (_brand, engine, _entity), mentioned in vectors.items():
        pool_sizes[engine] = max(pool_sizes[engine], len(mentioned))

    print("Пул даних (об'єднано через усі прогони, тижні 2-3):")
    for engine, n in sorted(pool_sizes.items()):
        print(f"  {engine}: N={n} на (subject_brand, mentioned_entity)-групу")
    print(f"  Груп (subject_brand x engine x конкурент): {len(vectors)}\n")

    curves = aggregate_curves_by_engine(vectors, seed=42)

    for engine, curve in sorted(curves.items()):
        print(f"{engine} (усереднено по групах-конкурентах, n=1..{curve[-1].n}):")
        print("  n | середня ширина CI (в.п.) | точкова оцінка")
        for p in curve:
            print(f"  {p.n:>3} | {p.avg_half_width_pp:>6.1f} | {p.point_estimate * 100:>5.1f}%")
        print()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for engine, curve in sorted(curves.items()):
        ns = [p.n for p in curve]
        widths = [p.avg_half_width_pp for p in curve]
        ax.plot(ns, widths, marker="o", markersize=3, label=engine)
    ax.axhline(5.0, color="gray", linestyle="--", linewidth=1, label="ціль ±5 в.п.")
    ax.set_xlabel("n (кількість відповідей на групу)")
    ax.set_ylabel("середня ширина bootstrap CI (в.п.)")
    ax.set_title("Тиждень 4: криві збіжності mention rate конкурента (Stripe/Paddle)")
    ax.legend()
    fig.tight_layout()

    out_path = REPORTS_DIR / "week4_convergence.png"
    fig.savefig(out_path, dpi=150)
    print(f"Графік збережено: {out_path}")


if __name__ == "__main__":
    main()

"""Perception map: how each AI engine rates the brands per attribute (Bradley-Terry + CI).

Run: uv run python scripts/perception_report.py [--run-id N [N ...]] [--seed 42] [--n-boot 1000]

Reads the answers stored by scripts/run_pairwise.py. Makes no Claude/OpenAI calls.
See docs/weeks/week7.md.
"""

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aivisibility.common import config, db
from aivisibility.perception.aggregate import (
    count_cycles,
    engine_agreement,
    engine_stats,
    overlapping_pairs,
    perception_map,
)

OUT_FILE = config.REPORTS_DIR / "week7_perception_map.png"


def print_stats(stats):
    print("Позиційне упередження (частка відповідей «A»; 0.5 = немає) і невалідні відповіді\n")
    for engine, s in stats.items():
        p = s["position"]
        print(f"  {engine:7s} n={s['n']:4d}  invalid={s['invalid_share']:.1%}  "
              f"p_first={p['p_first']:.3f} [{p['ci'][0]:.3f}, {p['ci'][1]:.3f}]")


def print_map(result_map, brands):
    print("\nКарта сприйняття: θ [95% CI, bootstrap по комірках] (більше = AI частіше обирає бренд)")
    print("† = розділення: якийсь бренд ніколи не програє/не виграє, величину θ задає регуляризація,")
    print("    довіряти можна лише порядку брендів\n")
    for (engine, attr), res in result_map.items():
        cells = "  ".join(
            f"{b} {res.theta[i]:+.2f} [{res.ci_low[i]:+.2f},{res.ci_high[i]:+.2f}]"
            for i, b in sorted(enumerate(brands), key=lambda t: -res.theta[t[0]])
        )
        mark = "†" if res.separated else " "
        print(f"  {engine:7s} {attr:22s}{mark} {cells}")
        ties = overlapping_pairs(res)
        if ties:
            print(f"  {'':31s} CI перекриваються (не ранжуємо): "
                  + ", ".join(f"{a}~{b}" for a, b in ties))


CLIP = 4.0  # colour scale limit; larger theta is drawn at full colour (the number is still printed)


def plot_map(result_map, brands, attributes, path):
    engines = sorted({e for e, _ in result_map})
    fig, axes = plt.subplots(1, len(engines), figsize=(5.5 * len(engines), 3.9), squeeze=False)
    for ax, engine in zip(axes[0], engines):
        grid = np.full((len(brands), len(attributes)), np.nan)
        marks = [["" for _ in attributes] for _ in brands]
        labels = []
        for j, attr in enumerate(attributes):
            res = result_map.get((engine, attr))
            labels.append(attr + (" †" if res is not None and res.separated else ""))
            if res is None:
                continue
            rank = (-res.theta).argsort().argsort() + 1
            for i in range(len(brands)):
                grid[i, j] = res.theta[i]
                if res.separated:  # size of theta is not interpretable: show the rank only
                    marks[i][j] = f"#{rank[i]}"
                else:
                    half = (res.ci_high[i] - res.ci_low[i]) / 2
                    marks[i][j] = f"{res.theta[i]:+.1f}\n±{half:.1f}"
        im = ax.imshow(grid, cmap="RdBu", vmin=-CLIP, vmax=CLIP, aspect="auto")
        for i in range(len(brands)):
            for j in range(len(attributes)):
                ax.text(j, i, marks[i][j], ha="center", va="center", fontsize=7)
        ax.set_xticks(range(len(attributes)), labels, rotation=40, ha="right", fontsize=8)
        ax.set_yticks(range(len(brands)), brands)
        ax.set_title(engine)
    fig.colorbar(im, ax=axes[0].tolist(), label=f"θ (Bradley-Terry), шкала обрізана до ±{CLIP:g}", extend="both")
    fig.suptitle("Карта сприйняття (θ ± половина 95% CI; † = лише ранг, #1 = найвищий)")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(run_ids: list[int] | None, seed: int, n_boot: int) -> None:
    db.init_db()
    rows = db.get_pairwise_responses(run_ids)
    if not rows:
        print("Немає відповідей у pairwise_responses. Спершу scripts/run_pairwise.py.")
        return
    brands = config.PERCEPTION_BRANDS
    attributes = list(config.PERCEPTION_ATTRIBUTES)
    print(f"Відповідей: {len(rows)} (runs {run_ids or 'усі'}), seed={seed}\n")

    print_stats(engine_stats(rows, n_boot, seed))
    result_map = perception_map(rows, brands, n_boot, seed)
    print_map(result_map, brands)

    cycles = count_cycles(rows, brands)
    total = sum(cycles.values())
    print(f"\nІнтранзитивні трійки (A>B>C>A за більшістю): {total} з {len(cycles)} комірок (engine, атрибут)")
    for (engine, attr), n in cycles.items():
        if n:
            print(f"  {engine} {attr}: {n}")

    engines = sorted({e for e, _ in result_map})
    if len(engines) == 2:
        print(f"\nЗгода движків {engines[0]} vs {engines[1]} (Spearman θ по брендах)")
        for attr, rho in engine_agreement(result_map, tuple(engines)).items():
            print(f"  {attr:22s} ρ={rho:+.2f}")

    plot_map(result_map, brands, attributes, OUT_FILE)
    print(f"\nГрафік: {OUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", type=int, nargs="+", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-boot", type=int, default=1000)
    args = parser.parse_args()
    main(args.run_id, args.seed, args.n_boot)

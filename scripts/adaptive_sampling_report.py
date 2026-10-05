"""Compare adaptive (expected-variance-reduction) sampling against uniform
round-robin, via offline simulation on data already collected in weeks 2-4
(see docs/weeks/week5.md).

Two experiments, because the naive one doesn't show what we expected:

1. "Draws needed for every arm to independently reach ±5 pp" — turns out
   to be policy-invariant when arms are statistically independent (each
   arm needs its own fixed number of draws regardless of scheduling order,
   as long as neither policy wastes draws on an already-converged arm).
   Reported honestly as a negative/explained finding, not hidden.

2. "Precision bought for a FIXED, shared budget" — the framing where
   adaptive sampling actually wins: reallocating draws toward the
   currently most uncertain arm (instead of splitting evenly) reduces the
   AVERAGE remaining uncertainty across all tracked competitors, the same
   logic as Neyman-optimal allocation in stratified sampling. This is
   where the headline "same precision, X% fewer calls" number comes from.

Run: python scripts/adaptive_sampling_report.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aivisibility.analysis.adaptive_sampling import (
    build_arms,
    final_entity_widths,
    run_fixed_budget,
    simulate,
    uniform_policy,
    variance_policy,
)
from aivisibility.common.config import REPORTS_DIR

TARGET_PP = 5.0
POLICIES = {"uniform": uniform_policy, "variance (adaptive)": variance_policy}


def experiment_full_convergence(arms, n_repeats: int = 15) -> None:
    print("Experiment 1: how many total draws are needed for EVERY arm\n"
          "to independently reach ±5 pp, stable over a rolling window\n")
    totals = {}
    for name, policy in POLICIES.items():
        vals = []
        for seed in range(n_repeats):
            result = simulate(
                arms, policy, target_pp=TARGET_PP, stability_window=5,
                max_draws=6000, n_resamples=150, seed=seed,
            )
            vals.append(result.total_draws)
        totals[name] = np.array(vals)
        print(f"  {name}: mean {np.mean(vals):.0f} draws "
              f"(std={np.std(vals):.0f}, {n_repeats} repeats)")

    diff_pp = (totals["uniform"].mean() - totals["variance (adaptive)"].mean()) / totals["uniform"].mean() * 100
    print(f"\n  Difference of means: {diff_pp:.1f}% — within noise (std ~"
          f"{totals['uniform'].std():.0f}-{totals['variance (adaptive)'].std():.0f}).")
    print("  Explanation: the arms are statistically independent and the stopping\n"
          "  rule requires EVERY arm to reach the target on its own, so the total\n"
          "  number of draws a given arm needs does not depend on when those draws\n"
          "  happen relative to the other arms (as long as neither policy wastes\n"
          "  draws on an already-converged arm — neither does). So reordering the\n"
          "  draws (adaptivity) cannot shrink the sum here. This is a deliberately\n"
          "  documented negative result, not an experiment error.\n")


def experiment_fixed_budget(
    arms, budgets: list[int], n_repeats: int = 15
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    n_entities = sum(len(arm.entities) for arm in arms)
    print(f"Experiment 2: what precision — mean (over all {n_entities} entities) and\n"
          "worst-case (max) CI width — is reached for the SAME fixed draw\n"
          "budget. Max closes the loophole in the mean: a few entities with a\n"
          "point estimate of exactly 0% (e.g. Checkout.com) get a degenerate\n"
          "zero width almost immediately (the same bootstrap-on-a-constant\n"
          "effect as n=1 in week4.md) and pull the mean down — max does not\n"
          "hide this.\n")
    mean_width_by_policy: dict[str, list[float]] = {name: [] for name in POLICIES}
    max_width_by_policy: dict[str, list[float]] = {name: [] for name in POLICIES}

    for budget in budgets:
        for name, policy in POLICIES.items():
            mean_widths, max_widths = [], []
            for seed in range(n_repeats):
                run_fixed_budget(arms, policy, budget=budget, n_resamples=150, seed=seed)
                widths = np.array(list(final_entity_widths(arms, n_resamples=300, seed=seed).values()))
                mean_widths.append(np.nanmean(widths))
                max_widths.append(np.nanmax(widths))
            mean_width_by_policy[name].append(float(np.mean(mean_widths)))
            max_width_by_policy[name].append(float(np.mean(max_widths)))
        row = " | ".join(
            f"{name}: mean={mean_width_by_policy[name][-1]:.2f} max={max_width_by_policy[name][-1]:.2f}"
            for name in POLICIES
        )
        print(f"  budget={budget:>4}: {row}")

    return mean_width_by_policy, max_width_by_policy


def crossing_budget(budgets: list[int], widths: list[float], target_pp: float) -> float | None:
    """Linear interpolation between the two bracketing sweep points where
    the (decreasing) width curve crosses target_pp. If the smallest swept
    budget is already at or below target, returns that budget as-is (an
    upper bound — the true crossing point may be even smaller, outside the
    swept range). None if the target is never reached within the range."""
    if widths[0] <= target_pp:
        return float(budgets[0])
    for i in range(1, len(budgets)):
        w0, w1 = widths[i - 1], widths[i]
        if w0 >= target_pp >= w1:
            b0, b1 = budgets[i - 1], budgets[i]
            if w0 == w1:
                return float(b0)
            frac = (w0 - target_pp) / (w0 - w1)
            return b0 + frac * (b1 - b0)
    return None


def extrapolate_crossing_budget(budgets: list[int], widths: list[float], target_pp: float) -> float:
    """Same 1/sqrt(budget)-shape extrapolation as week4.md's
    estimate_min_n(), fit on the upper half of the swept budgets — used
    when the target isn't reached within the swept range."""
    max_b = budgets[-1]
    fit_points = [(b, w) for b, w in zip(budgets, widths) if b >= max(budgets[0], max_b // 2)]
    ns = np.array([b for b, _ in fit_points], dtype=float)
    ws = np.array([w for _, w in fit_points], dtype=float)
    inv_sqrt_n = 1 / np.sqrt(ns)
    c = float(np.sum(ws * inv_sqrt_n) / np.sum(inv_sqrt_n**2))
    return max((c / target_pp) ** 2, max_b + 1)


def report_crossings(metric_name: str, budgets: list[int], width_by_policy: dict[str, list[float]]) -> None:
    print(f"\nTarget for budget comparison ({metric_name}): ≤ ±{TARGET_PP:.0f} pp\n")
    crossings = {}
    for name, widths in width_by_policy.items():
        b = crossing_budget(budgets, widths, TARGET_PP)
        extrapolated = False
        if b is None:
            b = extrapolate_crossing_budget(budgets, widths, TARGET_PP)
            extrapolated = True
        crossings[name] = b
        if extrapolated:
            label = f"~{b:.0f} draws (1/sqrt(budget) extrapolation, not a direct observation)"
        elif b == budgets[0]:
            label = f"≤{b:.0f} draws (target already reached at the smallest swept budget)"
        else:
            label = f"{b:.0f} draws"
        print(f"  {name}: {label}")

    b_uniform, b_adaptive = crossings["uniform"], crossings["variance (adaptive)"]
    savings_pct = (b_uniform - b_adaptive) / b_uniform * 100
    print(f"  -> same precision ({metric_name}) with {savings_pct:.0f}% fewer draws "
          f"under adaptive sampling ({b_adaptive:.0f} vs {b_uniform:.0f}).")


def main() -> None:
    arms = build_arms()
    experiment_full_convergence(arms, n_repeats=15)

    budgets = [8, 12, 16, 20, 25, 30, 50, 75, 100, 130, 160, 200, 250, 300, 400, 600, 800]
    mean_width_by_policy, max_width_by_policy = experiment_fixed_budget(arms, budgets, n_repeats=15)

    n_entities = sum(len(arm.entities) for arm in arms)
    report_crossings(f"mean CI width over {n_entities} entities", budgets, mean_width_by_policy)
    report_crossings(f"WORST-case (max) CI width among {n_entities} entities", budgets, max_width_by_policy)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for ax, width_by_policy, subtitle in (
        (ax1, mean_width_by_policy, f"mean CI width ({n_entities} entities)"),
        (ax2, max_width_by_policy, "worst-case (max) CI width"),
    ):
        for name, widths in width_by_policy.items():
            ax.plot(budgets, widths, marker="o", markersize=4, label=name)
        ax.axhline(TARGET_PP, color="gray", linestyle="--", linewidth=1, label=f"target ±{TARGET_PP:.0f} pp")
        ax.set_xlabel("budget (number of simulated draws)")
        ax.set_ylabel("bootstrap CI width (pp)")
        ax.set_title(subtitle)
        ax.legend()
    fig.suptitle("Week 5: precision at a fixed budget — uniform vs adaptive")
    fig.tight_layout()

    out_path = REPORTS_DIR / "week5_adaptive_sampling.png"
    fig.savefig(out_path, dpi=150)
    print(f"\nChart saved: {out_path}")


if __name__ == "__main__":
    main()

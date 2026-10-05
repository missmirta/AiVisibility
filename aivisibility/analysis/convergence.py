"""Convergence curves: bootstrap CI width as a function of sample size n,
built by subsampling the data already collected in weeks 2-3 (no new
Prober calls) — and an empirical minimum-n estimate from the curve shape.

See docs/weeks/week4.md for the full method and its honesty caveats.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..common import db
from .bootstrap import bootstrap_ci
from .mentions import build_candidate_dictionary, load_brand_profiles
from .precision import BOOTSTRAP_RESAMPLES, MAX_SUBSAMPLES, MC_TOLERANCE_PP, MIN_SUBSAMPLES


@dataclass
class ConvergencePoint:
    n: int
    avg_half_width_pp: float
    point_estimate: float


@dataclass
class CrossingResult:
    engine: str
    target_pp: float
    max_observed_n: int
    width_at_max_n: float
    observed_n: int | None
    extrapolated_n: int | None
    fit_note: str


def pooled_mention_vectors() -> dict[tuple[str, str, str], list[bool]]:
    """(subject_brand, engine, mentioned_entity) -> boolean "mentioned in
    this response" vector, pooled across EVERY run in the database (not
    scoped to one run_id like week 3's report.py) — convergence curves
    need more data points than any single run provides. Competitors only:
    own-brand mention rate is trivially high (see week3.md) and not
    interesting for a convergence curve either."""
    profiles = load_brand_profiles()
    candidates_by_brand = {
        brand: build_candidate_dictionary(profile) for brand, profile in profiles.items()
    }

    responses = db.get_responses_with_brand()
    groups: dict[tuple[str, str], list[int]] = {}
    for row in responses:
        if row["error"] or not row["raw_text"]:
            continue
        groups.setdefault((row["subject_brand"], row["engine"]), []).append(row["response_id"])

    all_response_ids = [rid for ids in groups.values() for rid in ids]
    mentions_by_response = db.get_mentions_for_responses(all_response_ids)

    vectors: dict[tuple[str, str, str], list[bool]] = {}
    for (subject_brand, engine), response_ids in groups.items():
        for entity in candidates_by_brand.get(subject_brand, []):
            if entity == subject_brand:
                continue
            vectors[(subject_brand, engine, entity)] = [
                entity in mentions_by_response[rid] for rid in response_ids
            ]
    return vectors


def _std_error(values: list[float]) -> float:
    return float(np.std(values, ddof=1) / np.sqrt(len(values)))


def subsample_curve(
    mentioned: list[bool],
    sizes: list[int] | None = None,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    tol_pp: float = MC_TOLERANCE_PP,
    min_subsamples: int = MIN_SUBSAMPLES,
    max_subsamples: int = MAX_SUBSAMPLES,
    seed: int | None = None,
) -> list[ConvergencePoint]:
    """For each n in `sizes`, draw random subsamples of size n without
    replacement from `mentioned`, run `bootstrap_ci()` on each, and average
    the resulting CI half-width — an empirical "would a smaller n have given
    us this much precision" curve. n = len(mentioned) has only one possible
    subsample (the whole pool), so it is not resampled.

    The number of subsamples per n is not fixed: drawing stops once the
    standard error of the average half-width drops to `tol_pp` (but never
    before `min_subsamples` or after `max_subsamples`), so the curve's own
    simulation noise is bounded regardless of pool size. See precision.py
    for why each default is what it is. `seed` makes the whole curve
    deterministic, including the inner bootstrap."""
    n_total = len(mentioned)
    if n_total == 0:
        return []
    if sizes is None:
        sizes = list(range(1, n_total + 1))

    values = np.asarray(mentioned, dtype=bool)
    rng = np.random.default_rng(seed)

    points: list[ConvergencePoint] = []
    for n in sizes:
        if n > n_total:
            continue
        max_draws = max_subsamples if n < n_total else 1
        widths: list[float] = []
        estimates: list[float] = []
        while len(widths) < max_draws:
            idx = rng.choice(n_total, size=n, replace=False)
            point, lower, upper = bootstrap_ci(
                values[idx].tolist(), n_resamples=n_resamples, seed=int(rng.integers(2**32))
            )
            widths.append((upper - lower) / 2 * 100)
            estimates.append(point)
            if len(widths) >= min_subsamples and _std_error(widths) <= tol_pp:
                break
        points.append(
            ConvergencePoint(
                n=n,
                avg_half_width_pp=float(np.mean(widths)),
                point_estimate=float(np.mean(estimates)),
            )
        )
    return points


def aggregate_curves_by_engine(
    vectors: dict[tuple[str, str, str], list[bool]],
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    tol_pp: float = MC_TOLERANCE_PP,
    seed: int | None = None,
) -> dict[str, list[ConvergencePoint]]:
    """One averaged curve per engine, across every (subject_brand,
    mentioned_entity) group for that engine — the master plan wants a
    per-engine orientation figure, not 20 separate per-pair curves."""
    curves_by_group: dict[tuple[str, str, str], list[ConvergencePoint]] = {
        key: subsample_curve(mentioned, n_resamples=n_resamples, tol_pp=tol_pp, seed=seed)
        for key, mentioned in vectors.items()
    }

    curves_by_engine: dict[str, list[list[ConvergencePoint]]] = defaultdict(list)
    for (_subject_brand, engine, _entity), curve in curves_by_group.items():
        if curve:
            curves_by_engine[engine].append(curve)

    result: dict[str, list[ConvergencePoint]] = {}
    for engine, curves in curves_by_engine.items():
        max_common_n = min(curve[-1].n for curve in curves)
        widths_by_n = {n: [] for n in range(1, max_common_n + 1)}
        estimates_by_n = {n: [] for n in range(1, max_common_n + 1)}
        for curve in curves:
            for p in curve:
                if p.n <= max_common_n:
                    widths_by_n[p.n].append(p.avg_half_width_pp)
                    estimates_by_n[p.n].append(p.point_estimate)
        result[engine] = [
            ConvergencePoint(
                n=n,
                avg_half_width_pp=float(np.mean(widths_by_n[n])),
                point_estimate=float(np.mean(estimates_by_n[n])),
            )
            for n in range(1, max_common_n + 1)
        ]
    return result


def estimate_min_n(engine: str, curve: list[ConvergencePoint], target_pp: float = 5.0) -> CrossingResult:
    """Smallest n where the curve's width already reaches `target_pp`
    (observed crossing point). If the target is never reached within the
    available data, fall back to fitting the well-known width ≈ c/sqrt(n)
    shape of a proportion's confidence interval to the observed points and
    solving for n — an extrapolation of the observed curve's shape, NOT
    Sielinski's unpublished parametric formula in citation-distribution
    parameters (see week4.md).

    n=1 is excluded from the search: a single-value bootstrap resample
    always equals itself, so its CI collapses to width 0 — a known
    degenerate artifact of the method at n=1, not real precision.

    The fit only uses the upper half of the observed n-range (n ≥
    max_n // 2). An unweighted least-squares fit of width ≈ c/sqrt(n) is,
    algebraically, a regression through the origin — points with small n
    (large 1/sqrt(n)) get outsized leverage even though they are the
    noisiest and closest to the n=1 degenerate regime. Anchoring the fit
    to larger, more reliable n avoids that bias."""
    observed_n = next(
        (p.n for p in curve if p.n >= 2 and p.avg_half_width_pp <= target_pp), None
    )
    max_n = curve[-1].n
    width_at_max_n = curve[-1].avg_half_width_pp

    extrapolated_n = None
    if observed_n is not None:
        fit_note = "observed directly within the available data"
    else:
        fit_points = [p for p in curve if p.n >= max(2, max_n // 2)]
        ns = np.array([p.n for p in fit_points], dtype=float)
        widths = np.array([p.avg_half_width_pp for p in fit_points], dtype=float)
        inv_sqrt_n = 1 / np.sqrt(ns)
        c = float(np.sum(widths * inv_sqrt_n) / np.sum(inv_sqrt_n**2))
        extrapolated_n = max(int(np.ceil((c / target_pp) ** 2)), max_n + 1)
        fit_note = (
            f"extrapolated from the 1/sqrt(n) curve shape (c≈{c:.2f}), fitted "
            f"on n∈[{fit_points[0].n}, {max_n}], not a direct observation"
        )

    return CrossingResult(
        engine=engine,
        target_pp=target_pp,
        max_observed_n=max_n,
        width_at_max_n=width_at_max_n,
        observed_n=observed_n,
        extrapolated_n=extrapolated_n,
        fit_note=fit_note,
    )

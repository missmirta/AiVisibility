"""Collect everything the dashboard shows into one JSON-ready dict (no API calls).

The dashboard only displays these numbers; all statistics stay in Python. Every
estimate carries its CI, or an explicit flag when no CI exists.
"""

import csv
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
from sklearn.metrics import cohen_kappa_score

from ..analysis import adaptive_sampling
from ..analysis.bootstrap import bootstrap_ci
from ..analysis.convergence import aggregate_curves_by_engine, estimate_min_n, pooled_mention_vectors
from ..analysis.report import compute_mention_rates
from ..common import config, db
from ..perception.aggregate import (
    count_cycles,
    engine_agreement,
    engine_stats,
    overlapping_pairs,
    perception_map,
)
from ..representativeness.reweight import (
    compute_cluster_weights,
    effective_sample_size,
    nearest_texts,
    weighted_bootstrap_ci,
    weighted_mention_vectors,
)
from ..representativeness.two_sample import (
    classifier_two_sample_test,
    embed_texts,
    is_choice_question,
    length_features,
    length_matched_indices,
)

SCHEMA_VERSION = 1
TARGET_PP = 5.0
# Sections that are not exported yet; listed so the dashboard shows them as missing, not as empty.
NOT_EXPORTED: list[str] = []
REAL_QUERIES_FILE = config.QUERIES_DIR / "real_queries.json"
GOLD_FILE = config.DATA_DIR / "labels" / "gold.csv"  # human labels
GOLD_TEACHER_FILE = config.DATA_DIR / "labels" / "gold_claude_key.csv"  # Claude labels, same row_id
# Same grid and repeat count as scripts/adaptive_sampling_report.py, so the numbers match week5.md.
ADAPTIVE_BUDGETS = [8, 12, 16, 20, 25, 30, 50, 75, 100, 130, 160, 200, 250, 300, 400, 600, 800]
ADAPTIVE_REPEATS = 15
# (k, kmeans seed) pairs for the weights sensitivity check, same as scripts/representativeness_report.py
SENSITIVITY_CONFIGS = [(3, 42), (4, 42), (5, 42), (6, 42), (7, 42), (7, 1), (7, 2)]


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True,
            cwd=config.PROJECT_ROOT,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _num(x: float) -> float | None:
    """JSON has no NaN/inf: map them to null."""
    return float(x) if np.isfinite(x) else None


def visibility_section(seed: int, n_resamples: int) -> list[dict]:
    rows = compute_mention_rates(n_resamples=n_resamples, seed=seed)
    return [
        {
            "subject_brand": r.subject_brand, "engine": r.engine, "entity": r.mentioned_entity,
            "n": r.n, "rate": r.point, "ci_low": r.lower, "ci_high": r.upper,
        }
        for r in sorted(rows, key=lambda r: (r.subject_brand, r.engine, r.mentioned_entity))
    ]


def convergence_section(seed: int, n_resamples: int) -> dict:
    curves = aggregate_curves_by_engine(pooled_mention_vectors(), n_resamples=n_resamples, seed=seed)
    out = {}
    for engine, curve in sorted(curves.items()):
        crossing = estimate_min_n(engine, curve, TARGET_PP)
        out[engine] = {
            "target_pp": TARGET_PP,
            "curve": [{"n": p.n, "half_width_pp": p.avg_half_width_pp} for p in curve],
            "observed_n": crossing.observed_n,
            "extrapolated_n": crossing.extrapolated_n,
            "note": crossing.fit_note,
        }
    return out


def perception_section(run_ids: list[int] | None, seed: int, n_boot: int) -> dict:
    rows = db.get_pairwise_responses(run_ids)
    if not rows:
        return {"available": False}
    brands = config.PERCEPTION_BRANDS
    result_map = perception_map(rows, brands, n_boot, seed)
    cells = []
    for (engine, attr), res in result_map.items():
        rank = (-res.theta).argsort().argsort() + 1
        cells.append({
            "engine": engine, "attribute": attr,
            # theta size is set by the regulariser when separated: only the rank is meaningful then
            "rank_only": bool(res.separated),
            "overlapping": [list(p) for p in overlapping_pairs(res)],
            "brands": [
                {"brand": b, "theta": float(res.theta[i]), "ci_low": float(res.ci_low[i]),
                 "ci_high": float(res.ci_high[i]), "rank": int(rank[i])}
                for i, b in enumerate(res.brands)
            ],
        })
    engines = sorted({e for e, _ in result_map})
    agreement = engine_agreement(result_map, tuple(engines)) if len(engines) == 2 else {}
    return {
        "available": True,
        "brands": brands,
        "n_responses": len(rows),
        "run_ids": run_ids or sorted({r["run_id"] for r in rows}),
        "cells": cells,
        "engine_stats": {
            e: {"n": s["n"], "invalid_share": s["invalid_share"], "p_first": s["position"]["p_first"],
                "p_first_ci": list(s["position"]["ci"])}
            for e, s in engine_stats(rows, n_boot, seed).items()
        },
        "intransitive_triples": sum(count_cycles(rows, brands).values()),
        "engine_agreement_spearman": {a: _num(v) for a, v in agreement.items()},
    }


def _interval(values: np.ndarray, ci: float = 0.95) -> tuple[float, float]:
    alpha = 1 - ci
    low, high = np.nanpercentile(values, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(low), float(high)


def _savings_pct(budgets: list[int], widths: dict[str, np.ndarray], repeats: np.ndarray) -> float:
    """Draws saved by adaptive vs uniform to reach the target, averaging the chosen repeats."""
    needed = {
        name: adaptive_sampling.budget_to_target(budgets, w[:, repeats].mean(axis=1).tolist(), TARGET_PP)[0]
        for name, w in widths.items()
    }
    return (needed["uniform"] - needed["variance (adaptive)"]) / needed["uniform"] * 100


def _fixed_budget_metric(budgets: list[int], widths: dict[str, np.ndarray], seed: int, n_resamples: int) -> dict:
    """One width metric (mean or worst case over entities): curves, draws to target, savings."""
    n_repeats = next(iter(widths.values())).shape[1]
    curves, draws = {}, {}
    for name, w in widths.items():
        curves[name] = [
            {"budget": b, "width_pp": float(w[i].mean()), "repeat_low": _interval(w[i])[0],
             "repeat_high": _interval(w[i])[1]}
            for i, b in enumerate(budgets)
        ]
        n, extrapolated = adaptive_sampling.budget_to_target(budgets, w.mean(axis=1).tolist(), TARGET_PP)
        draws[name] = {"draws": float(n), "extrapolated": extrapolated, "at_smallest_budget": n == budgets[0]}
    # Bootstrap over the simulation repeats (the same repeats for both policies: they share seeds).
    rng = np.random.default_rng(seed)
    boot = [_savings_pct(budgets, widths, rng.integers(0, n_repeats, n_repeats)) for _ in range(n_resamples)]
    low, high = _interval(np.asarray(boot))
    savings = _savings_pct(budgets, widths, np.arange(n_repeats))
    return {
        "curves": curves, "draws_to_target": draws,
        "savings_pct": {"value": savings, "ci_low": low, "ci_high": high},
    }


def adaptive_sampling_section(
    seed: int,
    n_resamples: int,
    budgets: list[int] | None = None,
    n_repeats: int = ADAPTIVE_REPEATS,
) -> dict:
    """Offline simulation on stored answers: does adaptive sampling reach ±5 pp with fewer calls?

    Two experiments, as in week5.md. `fixed_budget` is where adaptive wins; `full_convergence` is the
    one where it should not (independent arms), exported so the dashboard does not oversell the win.
    The CI is over simulation repeats only: it does not cover the finite pool of stored answers."""
    budgets = budgets or ADAPTIVE_BUDGETS
    arms = [a for a in adaptive_sampling.build_arms() if a.entities]
    if not arms:
        return {"available": False}
    policies = adaptive_sampling.POLICIES

    widths = adaptive_sampling.fixed_budget_widths(arms, policies, budgets, n_repeats, seed)
    fixed = {
        kind: _fixed_budget_metric(budgets, {name: w[kind] for name, w in widths.items()}, seed, n_resamples)
        for kind in ("mean", "max")
    }

    totals = adaptive_sampling.full_convergence_draws(arms, policies, n_repeats, TARGET_PP, seed)
    uniform, adaptive = totals["uniform"], totals["variance (adaptive)"]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_resamples):
        idx = rng.integers(0, n_repeats, n_repeats)
        diffs.append((uniform[idx].mean() - adaptive[idx].mean()) / uniform[idx].mean() * 100)
    low, high = _interval(np.asarray(diffs))
    return {
        "available": True,
        "target_pp": TARGET_PP, "n_repeats": n_repeats, "budgets": budgets,
        "n_arms": len(arms), "n_entities": sum(len(a.entities) for a in arms),
        "fixed_budget": fixed,
        "full_convergence": {
            "mean_draws": {name: float(t.mean()) for name, t in totals.items()},
            "std_draws": {name: float(t.std()) for name, t in totals.items()},
            "adaptive_saving_pct": {
                "value": float((uniform.mean() - adaptive.mean()) / uniform.mean() * 100),
                "ci_low": low, "ci_high": high, "distinguishable_from_zero": not low <= 0 <= high,
            },
        },
    }


def _teacher_agreement(seed: int, n_resamples: int) -> dict:
    """Cohen's kappa between the human gold labels and Claude's labels on the same snippets."""
    if not (GOLD_FILE.exists() and GOLD_TEACHER_FILE.exists()):
        return {"available": False}
    with open(GOLD_FILE, encoding="utf-8", newline="") as f:
        human = {r["row_id"]: r["human_label"] for r in csv.DictReader(f) if r["human_label"]}
    with open(GOLD_TEACHER_FILE, encoding="utf-8", newline="") as f:
        teacher = {r["row_id"]: r["claude_label"] for r in csv.DictReader(f)}
    ids = sorted(set(human) & set(teacher))
    if not ids:
        return {"available": False}
    h, t = np.asarray([human[i] for i in ids]), np.asarray([teacher[i] for i in ids])
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_resamples):
        idx = rng.integers(0, len(ids), len(ids))
        boot.append(cohen_kappa_score(h[idx], t[idx]))
    low, high = _interval(np.asarray(boot))  # a degenerate resample gives NaN: nanpercentile skips it
    return {
        "available": True, "n": len(ids),
        "kappa": _num(cohen_kappa_score(h, t)), "kappa_ci_low": low, "kappa_ci_high": high,
    }


def stance_section(seed: int, n_resamples: int) -> dict:
    """How favourably each brand is mentioned: share of recommended / neutral / negative snippets.

    Uses Claude's stored labels of the real snippets (no model run, no API). Snippets from one answer
    are correlated, so the bootstrap resamples whole answers. The labels are Claude's judgement, not
    ground truth: `teacher_agreement` shows how far a human labeler agrees."""
    if not config.STANCE_LABELS_FILE.exists():
        return {"available": False}
    context = {r["response_id"]: (r["subject_brand"], r["engine"]) for r in db.get_responses_with_brand()}
    labels = config.STANCE_LABELS
    # (subject brand, engine, mentioned brand) -> response id -> label counts. Synthetic rows have ids
    # that are not in the DB, so the lookup drops them.
    groups: dict[tuple[str, str, str], dict[int, np.ndarray]] = {}
    with open(config.STANCE_LABELS_FILE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            response_id = int(row["response_id"])
            if response_id not in context:
                continue
            by_response = groups.setdefault((*context[response_id], row["brand"]), {})
            counts = by_response.setdefault(response_id, np.zeros(len(labels)))
            counts[labels.index(row["label"])] += 1
    if not groups:
        return {"available": False}

    items = []
    for key in sorted(groups):
        matrix = np.vstack(list(groups[key].values()))
        point = matrix.sum(axis=0) / matrix.sum()
        low = high = None
        if len(matrix) >= 2:  # a single answer cannot be resampled
            idx = np.random.default_rng(seed).integers(0, len(matrix), size=(n_resamples, len(matrix)))
            sums = matrix[idx].sum(axis=1)
            low, high = np.percentile(sums / sums.sum(axis=1, keepdims=True), [2.5, 97.5], axis=0)
        items.append({
            "subject_brand": key[0], "engine": key[1], "brand": key[2],
            "n_snippets": int(matrix.sum()), "n_responses": len(matrix),
            "ci_available": low is not None,
            "shares": {
                lab: {
                    "rate": float(point[i]),
                    "ci_low": None if low is None else float(low[i]),
                    "ci_high": None if high is None else float(high[i]),
                }
                for i, lab in enumerate(labels)
            },
        })
    return {
        "available": True, "labels": labels, "source": "claude_labels",
        "n_snippets": sum(i["n_snippets"] for i in items), "items": items,
        "teacher_agreement": _teacher_agreement(seed, n_resamples),
    }


def _weights_by_query(query_ids: list[int], cw) -> dict[int, float]:
    return {qid: float(cw.weights[label]) for qid, label in zip(query_ids, cw.synthetic_labels)}


def representativeness_section(
    seed: int,
    permutations: int,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> dict:
    """Synthetic vs real queries: two-sample test, topic clusters, and how re-weighting moves the
    mention rates. The CI covers response noise only; `sensitivity` shows the clustering choice."""
    queries = [dict(r) for r in db.get_all_queries()]
    if not queries or not REAL_QUERIES_FILE.exists():
        return {"available": False}
    syn_texts = [q["text"] for q in queries]
    query_ids = [q["id"] for q in queries]
    real_texts = [q["text"] for q in json.loads(REAL_QUERIES_FILE.read_text(encoding="utf-8"))]
    syn_emb, real_emb = embed(syn_texts), embed(real_texts)

    choice = [i for i, t in enumerate(real_texts) if is_choice_question(t)]
    matched = length_matched_indices(syn_texts, real_texts)
    cases = {
        "all_real": (syn_emb, real_emb),
        "choice_only": (syn_emb, real_emb[choice]),
        "length_matched": (syn_emb, real_emb[matched]),
        "length_only": (length_features(syn_texts), length_features(real_texts)),
    }
    two_sample = {}
    for name, (a, b) in cases.items():
        r = classifier_two_sample_test(a, b, seed=seed, n_permutations=permutations)
        two_sample[name] = {
            "n_synthetic": r.n_synthetic, "n_real": r.n_real, "auc": r.auc,
            "null_mean_auc": r.null_mean_auc, "p_value": r.p_value,
        }

    cw = compute_cluster_weights(syn_emb, real_emb, seed=seed)
    all_texts, all_emb = syn_texts + real_texts, np.vstack([syn_emb, real_emb])
    clusters = [
        {
            "id": c, "p_synthetic": float(cw.p_synthetic[c]), "p_real": float(cw.p_real[c]),
            "weight": float(cw.weights[c]), "uncovered": c in cw.uncovered,
            "examples": nearest_texts(all_texts, all_emb, cw.centroids[c], 2),
        }
        for c in range(cw.k)
    ]

    vectors = weighted_mention_vectors(_weights_by_query(query_ids, cw))
    sens: dict[tuple, list[float]] = {}
    for k, kmeans_seed in SENSITIVITY_CONFIGS:
        alt = compute_cluster_weights(syn_emb, real_emb, seed=kmeans_seed, k_range=range(k, k + 1))
        for key, (values, weights) in weighted_mention_vectors(_weights_by_query(query_ids, alt)).items():
            sens.setdefault(key, []).append(weighted_bootstrap_ci(values, weights, seed=seed)[0])

    mentions = []
    for key in sorted(vectors):
        values, weights = vectors[key]
        p0, l0, u0 = bootstrap_ci(values, seed=seed)
        p1, l1, u1 = weighted_bootstrap_ci(values, weights, seed=seed)
        deltas = [(p - p0) * 100 for p in sens[key]]
        if max(abs(d) for d in deltas) < 1:
            verdict = "no_change"
        elif min(deltas) >= -0.05 or max(deltas) <= 0.05:  # 0.05 pp tolerates "no change" configs
            verdict = "stable_sign"
        else:
            verdict = "mixed_sign"
        mentions.append({
            "subject_brand": key[0], "engine": key[1], "entity": key[2],
            "unweighted": {"rate": p0, "ci_low": l0, "ci_high": u0},
            "weighted": {"rate": p1, "ci_low": l1, "ci_high": u1},
            "n_eff": effective_sample_size(weights),
            "sensitivity": {"min": min(sens[key]), "max": max(sens[key]), "verdict": verdict},
        })

    return {
        "available": True,
        "n_synthetic": len(syn_texts), "n_real": len(real_texts), "permutations": permutations,
        "two_sample": two_sample,
        "clusters": {
            "k": cw.k, "silhouette": float(cw.silhouette), "items": clusters,
            "uncovered_real_share": float(sum(cw.p_real[c] for c in cw.uncovered)),
        },
        "mentions": mentions,
    }


def build_dashboard_data(
    seed: int = 42,
    n_resamples: int = 1000,
    n_boot: int = 1000,
    perception_run_ids: list[int] | None = None,
    permutations: int = 200,
) -> dict:
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "seed": seed,
            "n_resamples": n_resamples,
            "models": {"claude": config.CLAUDE_MODEL, "openai": config.OPENAI_MODEL},
            "not_exported": NOT_EXPORTED,
        },
        "visibility": visibility_section(seed, n_resamples),
        "convergence": convergence_section(seed, n_resamples),
        "perception": perception_section(perception_run_ids, seed, n_boot),
        "representativeness": representativeness_section(seed, permutations),
        "adaptive_sampling": adaptive_sampling_section(seed, n_resamples),
        "stance": stance_section(seed, n_resamples),
    }

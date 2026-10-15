"""Topic clusters and re-weighting of the mention rate toward the real query mix.

Each synthetic query gets the weight of its cluster: p_real / p_synthetic (clipped).
A cluster with no synthetic queries cannot be weighted; it is reported as "not covered".
See docs/weeks/week6.md.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from ..analysis.mentions import build_candidate_dictionary, load_brand_profiles
from ..analysis.precision import BOOTSTRAP_RESAMPLES
from ..common import db

MAX_WEIGHT = 5.0  # stops one rare cluster from dominating the weighted rate


@dataclass
class ClusterWeights:
    k: int
    silhouette: float
    centroids: np.ndarray
    synthetic_labels: np.ndarray
    real_labels: np.ndarray
    p_synthetic: np.ndarray
    p_real: np.ndarray
    weights: np.ndarray  # per cluster; 0 where there are no synthetic queries
    uncovered: list[int]  # clusters with real queries but no synthetic ones


def compute_cluster_weights(
    synthetic: np.ndarray,
    real: np.ndarray,
    seed: int = 42,
    k_range: range = range(3, 9),
    max_weight: float = MAX_WEIGHT,
) -> ClusterWeights:
    """Cluster both sets together (k picked by silhouette), then weight clusters."""
    both = np.vstack([synthetic, real])
    best = None
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(both)
        score = float(silhouette_score(both, km.labels_))
        if best is None or score > best[0]:
            best = (score, k, km)
    score, k, km = best

    syn_labels = km.labels_[: len(synthetic)]
    real_labels = km.labels_[len(synthetic):]
    p_syn = np.bincount(syn_labels, minlength=k) / len(synthetic)
    p_real = np.bincount(real_labels, minlength=k) / len(real)
    weights = np.where(p_syn > 0, np.minimum(p_real / np.where(p_syn > 0, p_syn, 1), max_weight), 0.0)
    uncovered = [c for c in range(k) if p_syn[c] == 0 and p_real[c] > 0]
    return ClusterWeights(k, score, km.cluster_centers_, syn_labels, real_labels, p_syn, p_real, weights, uncovered)


def nearest_texts(texts: list[str], embeddings: np.ndarray, centroid: np.ndarray, n: int = 3) -> list[str]:
    """The n texts closest to a cluster centre; used to name the topic by eye."""
    order = np.argsort(np.linalg.norm(embeddings - centroid, axis=1))
    return [texts[i] for i in order[:n]]


def weighted_bootstrap_ci(
    values: list[bool],
    weights: list[float],
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    ci: float = 0.95,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """(weighted_point, lower, upper). Resamples responses with replacement (as bootstrap_ci)
    and keeps each response's weight, so the weight sum varies between resamples too."""
    n = len(values)
    if n == 0 or sum(weights) == 0:
        return 0.0, 0.0, 0.0
    x = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    point = float((w * x).sum() / w.sum())

    idx = np.random.default_rng(seed).integers(0, n, size=(n_resamples, n))
    sums = w[idx].sum(axis=1)
    means = np.where(sums > 0, (w[idx] * x[idx]).sum(axis=1) / np.where(sums > 0, sums, 1), 0.0)
    alpha = 1 - ci
    lower, upper = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return point, float(lower), float(upper)


def effective_sample_size(weights: list[float]) -> float:
    """Kish effective n: how many unweighted responses the weighted sample is worth."""
    w = np.asarray(weights, dtype=np.float64)
    return float(w.sum() ** 2 / (w**2).sum()) if w.sum() > 0 else 0.0


def weighted_mention_vectors(
    query_weights: dict[int, float],
) -> dict[tuple[str, str, str], tuple[list[bool], list[float]]]:
    """(subject_brand, engine, competitor) -> (mentioned flags, per-response weights).
    Same selection as convergence.pooled_mention_vectors, but each response carries the
    weight of its query. Queries without a weight (e.g. in no cluster) get weight 0."""
    profiles = load_brand_profiles()
    candidates = {brand: build_candidate_dictionary(p) for brand, p in profiles.items()}

    groups: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for row in db.get_responses_with_brand():
        if row["error"] or not row["raw_text"]:
            continue
        groups.setdefault((row["subject_brand"], row["engine"]), []).append(
            (row["response_id"], row["query_id"])
        )
    mentions = db.get_mentions_for_responses([rid for pairs in groups.values() for rid, _ in pairs])

    out: dict[tuple[str, str, str], tuple[list[bool], list[float]]] = {}
    for (brand, engine), pairs in groups.items():
        w = [query_weights.get(qid, 0.0) for _, qid in pairs]
        for entity in candidates.get(brand, []):
            if entity != brand:
                out[(brand, engine, entity)] = ([entity in mentions[rid] for rid, _ in pairs], w)
    return out

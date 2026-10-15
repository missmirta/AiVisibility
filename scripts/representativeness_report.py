"""How far are our synthetic queries from real ones, and what does it do to the mention rate?

Run: uv run python scripts/representativeness_report.py [--seed 42] [--permutations 200]

Needs data/queries/real_queries.json (scripts/collect_real_queries.py). No Claude/OpenAI
calls: embeddings are local and the mention rates come from responses already in the DB.
See docs/weeks/week6.md.
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aivisibility.analysis.bootstrap import bootstrap_ci
from aivisibility.common import config, db
from aivisibility.representativeness.reweight import (
    compute_cluster_weights,
    effective_sample_size,
    nearest_texts,
    weighted_bootstrap_ci,
    weighted_mention_vectors,
)
from aivisibility.representativeness.two_sample import (
    classifier_two_sample_test,
    embed_texts,
    is_choice_question,
    length_features,
    length_matched_indices,
)

REAL_FILE = config.QUERIES_DIR / "real_queries.json"


def two_sample_section(syn_texts, real_texts, syn_emb, real_emb, seed, permutations):
    choice = [i for i, t in enumerate(real_texts) if is_choice_question(t)]
    matched = length_matched_indices(syn_texts, real_texts)
    cases = {
        "усі реальні": (syn_emb, real_emb),
        "лише питання про вибір/порівняння": (syn_emb, real_emb[choice]),
        "реальні, підібрані за довжиною": (syn_emb, real_emb[matched]),
        "лише довжина (контроль стилю)": (
            length_features(syn_texts),
            length_features([real_texts[i] for i in range(len(real_texts))]),
        ),
    }
    results = {}
    print("Classifier two-sample test (AUC: 0.5 = не відрізнити, 1.0 = повністю різні)\n")
    for name, (a, b) in cases.items():
        r = classifier_two_sample_test(a, b, seed=seed, n_permutations=permutations)
        results[name] = r
        print(f"  {name:38s} n_syn={r.n_synthetic:3d} n_real={r.n_real:3d}  "
              f"AUC={r.auc:.3f}  (випадково ≈{r.null_mean_auc:.3f})  p={r.p_value:.4f}")
    return results


def cluster_section(syn_texts, real_texts, syn_emb, real_emb, seed):
    cw = compute_cluster_weights(syn_emb, real_emb, seed=seed)
    all_texts = syn_texts + real_texts
    all_emb = np.vstack([syn_emb, real_emb])
    print(f"\nКластери тем: k={cw.k} (silhouette={cw.silhouette:.3f})\n")
    print(f"  {'#':>2} {'p_syn':>6} {'p_real':>7} {'вага':>6}  приклади (найближчі до центру)")
    for c in range(cw.k):
        flag = "  <- немає в нашому наборі" if c in cw.uncovered else ""
        examples = " | ".join(nearest_texts(all_texts, all_emb, cw.centroids[c], 2))
        print(f"  {c:>2} {cw.p_synthetic[c]:6.1%} {cw.p_real[c]:7.1%} {cw.weights[c]:6.2f}  {examples}{flag}")
    if cw.uncovered:
        share = sum(cw.p_real[c] for c in cw.uncovered)
        print(f"\n  Реальних питань у темах без синтетичних запитів: {share:.1%} "
              "(для них перезважити неможливо)")
    return cw


def mention_section(query_ids, cw, seed):
    query_weights = {qid: float(cw.weights[label]) for qid, label in zip(query_ids, cw.synthetic_labels)}
    vectors = weighted_mention_vectors(query_weights)
    print("\nMention rate до і після перезважування (95% CI, bootstrap)\n")
    print(f"  {'бренд/движок/сутність':42s} {'без ваг':>20s}  {'з вагами':>20s}  {'Δ в.п.':>7s}  n_eff")
    rows = []
    for key in sorted(vectors):
        values, weights = vectors[key]
        p0, l0, u0 = bootstrap_ci(values, seed=seed)
        p1, l1, u1 = weighted_bootstrap_ci(values, weights, seed=seed)
        n_eff = effective_sample_size(weights)
        rows.append((key, p0, p1, n_eff))
        print(f"  {'/'.join(key):42s} {p0:6.1%} [{l0:5.1%},{u0:5.1%}]  {p1:6.1%} [{l1:5.1%},{u1:5.1%}]  "
              f"{(p1 - p0) * 100:+7.1f}  {n_eff:5.0f}")
    return rows


SENSITIVITY_CONFIGS = [(3, 42), (4, 42), (5, 42), (6, 42), (7, 42), (7, 1), (7, 2)]  # (k, kmeans seed)


def sensitivity_section(query_ids, syn_emb, real_emb, seed):
    """Weights depend on the clustering (silhouette is low), so repeat with other k and seeds.
    The CI above covers response noise only, not this choice."""
    unweighted = None
    spread: dict[tuple, list[float]] = {}
    for k, kmeans_seed in SENSITIVITY_CONFIGS:
        cw = compute_cluster_weights(syn_emb, real_emb, seed=kmeans_seed, k_range=range(k, k + 1))
        qw = {qid: float(cw.weights[label]) for qid, label in zip(query_ids, cw.synthetic_labels)}
        for key, (values, weights) in weighted_mention_vectors(qw).items():
            spread.setdefault(key, []).append(weighted_bootstrap_ci(values, weights, seed=seed)[0])
            if unweighted is None:
                unweighted = {}
            unweighted[key] = float(np.mean(values))
    print(f"\nЧутливість до кластеризації ({len(SENSITIVITY_CONFIGS)} конфігурацій k/seed)\n")
    print(f"  {'бренд/движок/сутність':42s} {'без ваг':>8s}  {'з вагами min–max':>17s}  напрямок")
    for key in sorted(spread):
        deltas = [(p - unweighted[key]) * 100 for p in spread[key]]
        if max(abs(d) for d in deltas) < 1:
            verdict = "без змін"
        elif min(deltas) >= -0.05 or max(deltas) <= 0.05:  # 0.05 pp tolerates "no change" configs
            verdict = "стабільний знак"
        else:
            verdict = "знак мінливий"
        print(f"  {'/'.join(key):42s} {unweighted[key]:8.1%}  {min(spread[key]):7.1%} – {max(spread[key]):6.1%}  {verdict}")


def plot(results, cw, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    names = list(results)
    aucs = [results[n].auc for n in names]
    ax1.barh(range(len(names)), aucs, color="#4c78a8")
    ax1.axvline(0.5, color="gray", linestyle="--", label="не відрізнити (0.5)")
    ax1.set_yticks(range(len(names)), names, fontsize=8)
    ax1.set_xlim(0.4, 1.0)
    ax1.set_xlabel("AUC")
    ax1.set_title("Наскільки синтетичні запити відрізняються від реальних")
    ax1.legend(fontsize=8)

    x = np.arange(cw.k)
    ax2.bar(x - 0.2, cw.p_synthetic, 0.4, label="синтетичні", color="#4c78a8")
    ax2.bar(x + 0.2, cw.p_real, 0.4, label="реальні", color="#f58518")
    ax2.set_xticks(x, [f"#{c}" for c in x])
    ax2.set_ylabel("частка")
    ax2.set_title("Частка кожної теми-кластера")
    ax2.legend(fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    print(f"\nГрафік: {path}")


def main(seed: int, permutations: int) -> None:
    queries = [dict(r) for r in db.get_all_queries()]
    syn_texts = [q["text"] for q in queries]
    query_ids = [q["id"] for q in queries]
    real_texts = [q["text"] for q in json.loads(REAL_FILE.read_text(encoding="utf-8"))]
    print(f"Синтетичних запитів: {len(syn_texts)}, реальних: {len(real_texts)}\n")

    syn_emb, real_emb = embed_texts(syn_texts), embed_texts(real_texts)
    results = two_sample_section(syn_texts, real_texts, syn_emb, real_emb, seed, permutations)
    cw = cluster_section(syn_texts, real_texts, syn_emb, real_emb, seed)
    mention_section(query_ids, cw, seed)
    sensitivity_section(query_ids, syn_emb, real_emb, seed)
    plot(results, cw, config.REPORTS_DIR / "week6_representativeness.png")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--permutations", type=int, default=200)
    a = p.parse_args()
    main(a.seed, a.permutations)

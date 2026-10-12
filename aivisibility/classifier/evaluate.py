"""Honest evaluation: group-aware CV, bootstrap CI on macro-F1, baseline.

Snippets from one answer share context, so folds are split by response_id;
a random row split lets near-duplicates leak from train into test.
"""

from collections import Counter

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold

from aivisibility.common import config

from .train import build_pipeline


def group_cv_predictions(
    texts: list[str],
    labels: list[str],
    groups: list[str],
    *,
    seed: int = 42,
    C: float = 1.0,
    class_weight: str | None = None,
    n_splits: int = 5,
    mask: bool = True,
    features: str = "tfidf",
) -> list[str]:
    """Out-of-fold prediction for every row; no group is in both train and test."""
    x, y, g = np.asarray(texts, dtype=object), np.asarray(labels), np.asarray(groups)
    pred = np.empty(len(y), dtype=object)
    folds = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for train_idx, test_idx in folds.split(x, y, g):
        pipe = build_pipeline(seed, C, class_weight, mask, features)
        pipe.fit(x[train_idx].tolist(), y[train_idx].tolist())
        pred[test_idx] = pipe.predict(x[test_idx].tolist())
    return pred.tolist()


def macro_f1_ci(
    y_true: list[str],
    y_pred: list[str],
    groups: list[str],
    *,
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """(point, lower, upper) macro-F1, bootstrapping whole groups (answers)."""
    y_true_a, y_pred_a = np.asarray(y_true), np.asarray(y_pred)
    members: dict[str, list[int]] = {}
    for i, g in enumerate(groups):
        members.setdefault(g, []).append(i)
    group_rows = [np.asarray(v) for v in members.values()]

    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(n_resamples):
        picked = rng.integers(0, len(group_rows), size=len(group_rows))
        idx = np.concatenate([group_rows[j] for j in picked])
        scores.append(f1_score(y_true_a[idx], y_pred_a[idx], average="macro", zero_division=0))

    alpha = 1 - ci
    lower, upper = np.percentile(scores, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    point = float(f1_score(y_true_a, y_pred_a, average="macro", zero_division=0))
    return point, float(lower), float(upper)


def majority_baseline(y_true: list[str]) -> dict[str, float]:
    """Always predict the most common class: the score a model must beat."""
    top, count = Counter(y_true).most_common(1)[0]
    pred = [top] * len(y_true)
    return {
        "accuracy": count / len(y_true),
        "f1_macro": float(f1_score(y_true, pred, average="macro", labels=config.STANCE_LABELS, zero_division=0)),
    }


def class_report(y_true: list[str], y_pred: list[str]) -> dict:
    """Per-class precision/recall/F1/support plus the confusion matrix."""
    labels = config.STANCE_LABELS
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "per_class": {
            lab: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
            for i, lab in enumerate(labels)
        },
        "confusion_labels": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }

"""Classifier two-sample test: can a model tell synthetic queries from real ones?

AUC 0.5 means the two sets look the same; 1.0 means they are fully different.
The p-value comes from a permutation test: shuffle the labels, rescore, and count
how often chance alone reaches the observed AUC. See docs/sections/section6.md.
"""

import re
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CHOICE_RE = re.compile(
    r"\bvs\.?\b|\balternatives?\b|\bcompare\b|\bbest\b|\bwhich\b|\bshould\b|\brecommend|\bbetter\b|\bor\b",
    re.IGNORECASE,
)


@dataclass
class TwoSampleResult:
    auc: float
    p_value: float
    null_mean_auc: float
    n_synthetic: int
    n_real: int


def embed_texts(texts: list[str]) -> np.ndarray:
    """Unit-length sentence embeddings (local model, no API calls)."""
    from aivisibility.classifier.embeddings import Embedder

    vectors = Embedder().transform(texts)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def length_features(texts: list[str]) -> np.ndarray:
    """Style-only features (characters and words); a baseline for the style confound."""
    return np.array([[len(t), len(t.split())] for t in texts], dtype=float)


def is_choice_question(text: str) -> bool:
    """Real questions that compare or ask which provider to pick (not developer how-to)."""
    return bool(CHOICE_RE.search(text))


def length_matched_indices(synthetic: list[str], real: list[str]) -> list[int]:
    """Indices of real texts: for each synthetic text, the unused real text closest in length."""
    available = sorted(range(len(real)), key=lambda i: len(real[i]))
    chosen: list[int] = []
    for text in sorted(synthetic, key=len):
        best = min(available, key=lambda i: abs(len(real[i]) - len(text)))
        available.remove(best)
        chosen.append(best)
    return sorted(chosen)


def _cv_auc(X: np.ndarray, y: np.ndarray, seed: int, n_splits: int) -> float:
    aucs = []
    folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for train, test in folds.split(X, y):
        model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
        model.fit(X[train], y[train])
        aucs.append(roc_auc_score(y[test], model.decision_function(X[test])))
    return float(np.mean(aucs))


def classifier_two_sample_test(
    synthetic: np.ndarray,
    real: np.ndarray,
    seed: int = 42,
    n_splits: int = 5,
    n_permutations: int = 200,
) -> TwoSampleResult:
    """Cross-validated AUC of a classifier "synthetic (0) vs real (1)" on feature rows,
    plus a permutation p-value (labels shuffled, same folds)."""
    X = np.vstack([synthetic, real])
    y = np.array([0] * len(synthetic) + [1] * len(real))
    observed = _cv_auc(X, y, seed, n_splits)

    rng = np.random.default_rng(seed)
    null = np.array([_cv_auc(X, rng.permutation(y), seed, n_splits) for _ in range(n_permutations)])
    p_value = (1 + int((null >= observed).sum())) / (1 + n_permutations)
    return TwoSampleResult(observed, p_value, float(null.mean()), len(synthetic), len(real))

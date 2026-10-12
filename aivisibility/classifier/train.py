"""Train the stance classifier and log it to MLflow.

Every run logs params, metrics and the model. Registering it in the Model
Registry gives it a version, which the API loads by alias.
"""

import mlflow
from mlflow.tracking import MlflowClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from aivisibility.common import config

from .masking import mask_all


def build_pipeline(
    seed: int, C: float = 1.0, class_weight: str | None = None, mask: bool = True
) -> Pipeline:
    """TF-IDF + logistic regression; `mask` hides brand names before vectorizing."""
    steps = [("mask", FunctionTransformer(mask_all))] if mask else []
    return Pipeline(
        steps
        + [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(C=C, class_weight=class_weight, max_iter=1000, random_state=seed)),
        ]
    )


def split(texts, labels, groups, test_size: float, seed: int):
    """Train/test split; grouped by answer when `groups` is given."""
    if groups is None:
        return train_test_split(texts, labels, test_size=test_size, random_state=seed, stratify=labels)
    folds = StratifiedGroupKFold(n_splits=max(2, round(1 / test_size)), shuffle=True, random_state=seed)
    train_idx, test_idx = next(folds.split(texts, labels, groups))
    pick = lambda items, idx: [items[i] for i in idx]  # noqa: E731
    return pick(texts, train_idx), pick(texts, test_idx), pick(labels, train_idx), pick(labels, test_idx)


def train(
    texts: list[str],
    labels: list[str],
    *,
    seed: int = 42,
    C: float = 1.0,
    class_weight: str | None = None,
    test_size: float = 0.25,
    register: bool = True,
    groups: list[str] | None = None,
    mask: bool = True,
) -> dict[str, float]:
    """Fit, evaluate on a held-out split, log everything to MLflow.

    With `groups` (response_id) the split keeps every answer on one side, so
    near-duplicate snippets cannot leak from train into test.
    """
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.STANCE_EXPERIMENT)

    x_train, x_test, y_train, y_test = split(texts, labels, groups, test_size, seed)
    pipe = build_pipeline(seed, C, class_weight, mask)

    with mlflow.start_run():
        mlflow.log_params({"seed": seed, "C": C, "class_weight": str(class_weight), "test_size": test_size, "mask": mask, "grouped": groups is not None, "n_train": len(x_train)})
        pipe.fit(x_train, y_train)
        pred = pipe.predict(x_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "f1_macro": float(f1_score(y_test, pred, average="macro")),
        }
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(
            pipe,
            name="model",
            skops_trusted_types=["aivisibility.classifier.masking.mask_all"],
            registered_model_name=config.STANCE_MODEL_NAME if register else None,
        )
    return metrics


def latest_version() -> int:
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    versions = MlflowClient().search_model_versions(f"name='{config.STANCE_MODEL_NAME}'")
    return max(int(v.version) for v in versions)


def promote(version: int, alias: str = "production") -> None:
    """Point a registry alias (what the API loads) at a model version."""
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    MlflowClient().set_registered_model_alias(config.STANCE_MODEL_NAME, alias, str(version))

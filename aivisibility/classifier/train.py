"""Train the stance classifier and log it to MLflow.

Every run logs params, metrics and the model. Registering it in the Model
Registry gives it a version, which the API loads by alias.
"""

import mlflow
from mlflow.tracking import MlflowClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from aivisibility.common import config


def build_pipeline(seed: int, C: float = 1.0) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(C=C, max_iter=1000, random_state=seed)),
        ]
    )


def train(
    texts: list[str],
    labels: list[str],
    *,
    seed: int = 42,
    C: float = 1.0,
    test_size: float = 0.25,
    register: bool = True,
) -> dict[str, float]:
    """Fit, evaluate on a held-out split, log everything to MLflow."""
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.STANCE_EXPERIMENT)

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=seed, stratify=labels
    )
    pipe = build_pipeline(seed, C)

    with mlflow.start_run():
        mlflow.log_params({"seed": seed, "C": C, "test_size": test_size, "n_train": len(x_train)})
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

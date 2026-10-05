import pytest
from fastapi.testclient import TestClient

from aivisibility.classifier import serve
from aivisibility.classifier.train import promote, train
from aivisibility.common import config

TEXTS = [
    "Stripe is the best choice, I highly recommend it",
    "Highly recommended: Paddle is great for SaaS",
    "Top pick, excellent and reliable, go with Stripe",
    "Stripe and Paddle are both payment providers",
    "Paddle is a merchant of record platform",
    "Stripe offers APIs for online payments",
    "Avoid this provider, terrible support and hidden fees",
    "Not recommended, Paddle had awful downtime",
    "Stripe is a bad option here, expensive and unreliable",
]
LABELS = ["recommended"] * 3 + ["neutral"] * 3 + ["negative"] * 3


@pytest.fixture
def tracking(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    monkeypatch.setattr(config, "MLFLOW_TRACKING_URI", uri)
    monkeypatch.setattr(config, "STANCE_EXPERIMENT", "test-stance")
    return uri


def test_train_is_deterministic(tracking):
    a = train(TEXTS, LABELS, seed=1, test_size=0.34, register=False)
    b = train(TEXTS, LABELS, seed=1, test_size=0.34, register=False)
    assert a == b
    assert set(a) == {"accuracy", "f1_macro"}


def test_register_promote_and_serve(tracking, monkeypatch):
    train(TEXTS, LABELS, seed=1, test_size=0.34)
    promote(1)
    monkeypatch.setattr(config, "STANCE_MODEL_URI", f"models:/{config.STANCE_MODEL_NAME}@production")

    with TestClient(serve.app) as client:
        assert client.get("/health").json()["model_loaded"] is True
        res = client.post("/predict", json={"texts": ["highly recommend Stripe, excellent"]})
        assert res.status_code == 200
        assert res.json()["labels"][0] in config.STANCE_LABELS


def test_predict_503_without_model(tracking, monkeypatch):
    monkeypatch.setattr(config, "STANCE_MODEL_URI", "models:/does-not-exist@production")
    with TestClient(serve.app) as client:
        assert client.get("/health").json()["model_loaded"] is False
        assert client.post("/predict", json={"texts": ["x"]}).status_code == 503

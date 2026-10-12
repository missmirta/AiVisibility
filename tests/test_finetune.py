"""Fine-tuned classifier: trains one tiny epoch and survives a cloudpickle round trip.

Uses the locally cached base model only (no network); skipped if it is not cached.
"""

import cloudpickle
import pytest

pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from aivisibility.classifier.finetune import DEFAULT_MODEL, TransformerClassifier  # noqa: E402

try:
    transformers.AutoTokenizer.from_pretrained(DEFAULT_MODEL, local_files_only=True)
except Exception:
    pytest.skip("base model is not cached locally", allow_module_level=True)

TEXTS = [
    "TARGETBRAND is great, I recommend it",
    "TARGETBRAND is the best choice for you",
    "TARGETBRAND is a payments platform",
    "TARGETBRAND works with cards and wallets",
    "avoid TARGETBRAND, it is clunky and dated",
    "TARGETBRAND is worse than OTHERBRAND",
]
LABELS = ["recommended", "recommended", "neutral", "neutral", "negative", "negative"]


def test_fit_predict_and_pickle_round_trip():
    clf = TransformerClassifier(epochs=1, batch_size=3, seed=0).fit(TEXTS, LABELS)
    pred = clf.predict(TEXTS)
    assert len(pred) == len(TEXTS)
    assert set(pred) <= set(LABELS)

    restored = cloudpickle.loads(cloudpickle.dumps(clf))
    assert list(restored.predict(TEXTS)) == list(pred)

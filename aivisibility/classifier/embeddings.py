"""Sentence embeddings as features: each text becomes a vector that captures its meaning."""

from functools import cache

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


@cache
def _load(model_name: str):
    from fastembed import TextEmbedding  # lazy: the model is downloaded on first use

    return TextEmbedding(model_name)


class Embedder(BaseEstimator, TransformerMixin):
    """Pretrained encoder. Nothing is learned here, so `fit` does nothing."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return np.array(list(_load(self.model_name).embed(list(X))))

"""Fine-tune a small pretrained transformer as the stance classifier.

Unlike the frozen embeddings, all of the model's weights are adjusted on our labels,
so it can learn that "X has no equivalent" is negative for X.
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin

DEFAULT_MODEL = "distilroberta-base"


class TransformerClassifier(BaseEstimator, ClassifierMixin):
    """sklearn-style wrapper (fit/predict) so it can sit at the end of a Pipeline."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        epochs: int = 4,
        lr: float = 3e-5,
        batch_size: int = 16,
        max_len: int = 128,
        balanced: bool = True,
        seed: int = 42,
    ):
        self.model_name = model_name
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.max_len = max_len
        self.balanced = balanced
        self.seed = seed

    def _encode(self, texts):
        return self.tokenizer_(
            list(texts), truncation=True, max_length=self.max_len, padding=True, return_tensors="pt"
        )

    def fit(self, X, y):
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            get_linear_schedule_with_warmup,
        )

        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        self.classes_, y_idx = np.unique(np.asarray(y), return_inverse=True)
        self.tokenizer_ = AutoTokenizer.from_pretrained(self.model_name)
        self.model_ = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, num_labels=len(self.classes_)
        )

        counts = np.bincount(y_idx, minlength=len(self.classes_))
        weights = len(y_idx) / (len(self.classes_) * counts) if self.balanced else np.ones(len(counts))
        loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float))

        texts = np.asarray(X, dtype=object)
        steps = self.epochs * int(np.ceil(len(texts) / self.batch_size))
        optimizer = torch.optim.AdamW(self.model_.parameters(), lr=self.lr, weight_decay=0.01)
        schedule = get_linear_schedule_with_warmup(optimizer, int(0.1 * steps), steps)

        self.model_.train()
        for _ in range(self.epochs):
            order = rng.permutation(len(texts))
            for start in range(0, len(order), self.batch_size):
                idx = order[start : start + self.batch_size]
                batch = self._encode(texts[idx].tolist())
                logits = self.model_(**batch).logits
                loss = loss_fn(logits, torch.tensor(y_idx[idx]))
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model_.parameters(), 1.0)
                optimizer.step()
                schedule.step()
                optimizer.zero_grad()
        return self

    def predict(self, X):
        import torch

        self.model_.eval()
        texts = list(X)
        out = []
        with torch.no_grad():
            for start in range(0, len(texts), 64):
                logits = self.model_(**self._encode(texts[start : start + 64])).logits
                out.extend(logits.argmax(dim=-1).tolist())
        return self.classes_[np.asarray(out)]

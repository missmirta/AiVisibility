# Stance classifier

## Purpose

AiVisibility measures how AI assistants mention brands (Stripe, Paddle). Counting
mentions is not enough: "Stripe is the best choice" and "avoid Stripe for X" both
count as one mention. The ML model adds the missing piece, **stance**: how a brand is
presented in an answer.

Labels:
- `recommended` - the brand is suggested, praised or shown as a good choice
- `neutral` - the brand is only mentioned or described
- `negative` - the brand is criticised or shown as a poor choice

## How it works

1. **Snippets** (`aivisibility/classifier/snippets.py`) - cut a short window of sentences
   around each brand mention. The label belongs to one (brand, snippet) pair, because one
   answer can treat several brands differently.
2. **Labeling** (`labeler.py`, `scripts/label_stance.py`) - Claude acts as a "teacher" and
   labels snippets in batches. This costs money, so it needs an explicit budget.
3. **Training** (`train.py`) - a cheap student model (TF-IDF + logistic regression) learns
   from those labels. Runs, metrics and models are logged to MLflow.
4. **Serving** (`serve.py`) - a FastAPI service loads the registered model and returns
   labels for new texts.

## Why a small model instead of calling Claude every time

- The probing pipeline produces many responses; labeling all of them with an LLM is slow
  and expensive.
- A local model is free per prediction, fast and reproducible.
- Claude labels once, the small model scales that judgement to the rest of the data.

## Output

A stance per brand mention, so visibility results can be reported as
"how often **and how favourably**" a brand appears.

## Models

`build_pipeline(features=...)` in `train.py` picks the student model. Brand names are masked
first (`TARGETBRAND` / `OTHERBRAND`, see `masking.py`) in every variant.

| `--features` | Model | Notes |
|---|---|---|
| `tfidf` (default) | TF-IDF + logistic regression | Counts words; misses tone and negation. |
| `embed` | `bge-small-en-v1.5` sentence embeddings (fastembed) + logistic regression | Frozen encoder, only the sorter is trained. |
| `finetune` | `distilroberta-base`, all weights fine-tuned (`finetune.py`) | Best quality, CPU training takes minutes. Saved to MLflow with cloudpickle (about 330 MB). |

## Data

`data/labels/stance.csv` (1621 rows): Claude-labeled real snippets from the stored answers
plus 639 **synthetic** rows (ids >= 100000, from `stance_synthetic_*.csv`). The synthetic rows are
only `recommended` or `negative`, never `neutral`.

`data/labels/gold.csv` is the human gold set: 120 snippets labeled by hand, balanced
(`scripts/make_gold_set.py`). Cohen's kappa human vs Claude = 0.74.

## How to evaluate

```
uv run python scripts/evaluate_classifier.py --features finetune --seed 42
```

No API calls. It prints group-aware 5-fold CV (macro-F1 with a bootstrap CI, per-class report,
majority baseline) and, if the gold sheet is filled, a model trained **without** the gold answers
and scored on the human labels. Everything is logged to MLflow (`mlflow ui`, then open
http://localhost:5000). Check the `features` param of a run to see what it used.

Train and register a model with `scripts/train_classifier.py --features ... [--promote]`.
`--promote` points the `production` alias (what the API serves) at the new version.

## Results (2026-10-12)

Gold set, 1621 training rows, 120 human-labeled rows:

| Model | Gold macro-F1 | Gold `negative` recall |
|---|---|---|
| tfidf | 0.43 | 0.14 |
| embed | 0.46 | 0.14 |
| finetune (seeds 1, 2, 3, 42) | 0.53 - 0.62, mean 0.58 | 0.32 - 0.43, mean 0.39 |

- The seed alone moves the fine-tuned gold macro-F1 by about 9 points. Do not trust a single run.
- **The gold set is the honest number.** Pooled CV (about 0.80 - 0.86) is inflated by the synthetic
  rows, which are never `neutral`. On real rows only, CV macro-F1 is about 0.63 for tfidf and embed.
- Remaining weakness: mild comparative negatives ("less feature-rich than X", "no equivalent",
  "older-feeling") are predicted `neutral`. `negative` precision is high (about 0.78), recall is low.
- 3 of the 17 missed gold negatives follow from the labeling prompt itself: it labels
  "worth it only if..." and pure price/architecture differences `neutral` (`labeler.py`, rules 1 and 2
  and the PayPal example), while the human labeled them `negative`.

## Open questions

- Labeling policy: should "worse or costlier on the facts" be `negative` without explicit criticism?
  Changing it means relabeling (costs money).
- Report CV on real rows separately, so the pooled score is not mistaken for quality.
- Only 43 unlabeled snippets are left in the DB; more real data needs new probing.

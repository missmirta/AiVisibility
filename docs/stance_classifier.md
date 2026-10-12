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

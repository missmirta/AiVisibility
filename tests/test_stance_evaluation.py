from collections import Counter

from aivisibility.classifier.data import sample_gold
from aivisibility.classifier.evaluate import (
    class_report,
    group_cv_predictions,
    macro_f1_ci,
    majority_baseline,
)

LABELS = ["recommended", "neutral", "negative"]
WORDS = {"recommended": "great recommend best", "neutral": "provider platform offers", "negative": "avoid awful bad"}


def _dataset(n_groups: int = 30):
    texts, labels, groups = [], [], []
    for g in range(n_groups):
        label = LABELS[g % 3]
        for j in range(2):  # two snippets per answer
            texts.append(f"{WORDS[label]} item{g} part{j}")
            labels.append(label)
            groups.append(str(g))
    return texts, labels, groups


def test_group_cv_covers_every_row_and_is_seeded():
    texts, labels, groups = _dataset()
    a = group_cv_predictions(texts, labels, groups, seed=3, n_splits=3)
    b = group_cv_predictions(texts, labels, groups, seed=3, n_splits=3)
    assert a == b and len(a) == len(texts)
    assert all(p in LABELS for p in a)


def test_macro_f1_ci_brackets_point_and_is_deterministic():
    texts, labels, groups = _dataset()
    pred = group_cv_predictions(texts, labels, groups, seed=3, n_splits=3)
    a = macro_f1_ci(labels, pred, groups, n_resamples=200, seed=1)
    b = macro_f1_ci(labels, pred, groups, n_resamples=200, seed=1)
    assert a == b
    point, lo, hi = a
    assert lo <= point <= hi


def test_perfect_predictions_give_f1_one():
    _, labels, groups = _dataset()
    point, lo, hi = macro_f1_ci(labels, labels, groups, n_resamples=50, seed=1)
    assert point == lo == hi == 1.0


def test_majority_baseline():
    y = ["neutral"] * 6 + ["negative"] * 2 + ["recommended"] * 2
    base = majority_baseline(y)
    assert base["accuracy"] == 0.6
    assert base["f1_macro"] < 0.3


def test_class_report_shapes():
    rep = class_report(["neutral", "negative"], ["neutral", "neutral"])
    assert rep["per_class"]["negative"]["recall"] == 0.0
    assert rep["per_class"]["recommended"]["support"] == 0
    assert rep["confusion_matrix"][1] == [0, 1, 0]  # neutral row


def test_sample_gold_balances_and_spreads_shortfall():
    rows = (
        [{"label": "neutral", "text": f"n{i}"} for i in range(100)]
        + [{"label": "recommended", "text": f"r{i}"} for i in range(40)]
        + [{"label": "negative", "text": f"x{i}"} for i in range(10)]
    )
    gold = sample_gold(rows, n=60, seed=1)
    counts = Counter(r["label"] for r in gold)
    assert len(gold) == 60
    assert counts["negative"] == 10  # smallest class gives everything
    assert counts["recommended"] == counts["neutral"] == 25
    assert gold == sample_gold(rows, n=60, seed=1)


def test_mask_brands_separates_target_from_others():
    from aivisibility.classifier.masking import mask_brands

    out = mask_brands("[Stripe] Stripe is better than paddle and Lemon Squeezy.")
    assert out == "TARGETBRAND TARGETBRAND is better than OTHERBRAND and OTHERBRAND."


def test_mask_brands_respects_word_boundaries_and_missing_prefix():
    from aivisibility.classifier.masking import mask_brands

    assert mask_brands("[Square] a square deal") == "TARGETBRAND a TARGETBRAND deal"
    assert mask_brands("Stripe beats Paddle") == "OTHERBRAND beats OTHERBRAND"
    assert "Stripe" not in mask_brands("[Adyen] Stripe is cheaper")


def test_pipeline_masks_and_grouped_split_has_no_leak():
    from aivisibility.classifier.train import build_pipeline, split

    texts, labels, groups = _dataset()
    pipe = build_pipeline(1).fit(["[Stripe] great recommend", "[Paddle] avoid awful"], ["recommended", "negative"])
    assert pipe.predict(["[Paddle] great recommend"])[0] == "recommended"

    xtr, xte, ytr, yte = split(texts, labels, groups, 0.25, 1)
    assert not ({t.split()[-2] for t in xtr} & {t.split()[-2] for t in xte})

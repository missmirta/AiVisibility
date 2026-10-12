"""Evaluate the stance classifier and log the report to MLflow.

Run: uv run python scripts/evaluate_classifier.py [--class-weight balanced]

1. Group-aware cross-validation on the Claude-labeled data (macro-F1 with a
   bootstrap CI, per-class report, majority baseline).
2. If the gold sheet (scripts/make_gold_set.py) is filled in: Cohen's kappa
   between human and Claude labels, and a model trained WITHOUT the gold
   answers, scored against the human labels.

No API calls are made here.
"""

import argparse
import sys
from pathlib import Path

import mlflow
from sklearn.metrics import cohen_kappa_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.data import load_rows
from aivisibility.classifier.evaluate import (
    class_report,
    group_cv_predictions,
    macro_f1_ci,
    majority_baseline,
)
from aivisibility.classifier.train import build_pipeline
from aivisibility.common import config

GOLD_FILE = config.STANCE_LABELS_FILE.with_name("gold.csv")
KEY_FILE = config.STANCE_LABELS_FILE.with_name("gold_claude_key.csv")


def print_report(title: str, y_true: list[str], y_pred: list[str], report: dict) -> None:
    print(f"\n{title}")
    for lab, m in report["per_class"].items():
        print(f"  {lab:<12} P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} n={m['support']}")
    print(f"  confusion (rows=true, cols=pred, order={report['confusion_labels']}):")
    for row in report["confusion_matrix"]:
        print(f"    {row}")


def gold_evaluation(rows, args) -> dict[str, float] | None:
    if not GOLD_FILE.exists():
        return None
    gold = [r for r in load_rows(GOLD_FILE) if r["human_label"]]
    if not gold:
        print("\nGold sheet exists but has no human labels yet - skipping gold evaluation.")
        return None
    bad = {r["human_label"] for r in gold} - set(config.STANCE_LABELS)
    if bad:
        raise SystemExit(f"Unknown human labels in {GOLD_FILE}: {sorted(bad)}")

    claude = {r["row_id"]: r["claude_label"] for r in load_rows(KEY_FILE)}
    human = [r["human_label"] for r in gold]
    teacher = [claude[r["row_id"]] for r in gold]
    kappa = float(cohen_kappa_score(human, teacher))
    print(f"\nGold set: {len(gold)} human-labeled rows. Cohen's kappa human vs Claude = {kappa:.2f}")

    gold_responses = {r["response_id"] for r in gold}
    train_rows = [r for r in rows if r["response_id"] not in gold_responses]
    pipe = build_pipeline(args.seed, args.C, args.class_weight, not args.no_mask)
    pipe.fit([r["text"] for r in train_rows], [r["label"] for r in train_rows])
    pred = pipe.predict([r["text"] for r in gold]).tolist()
    f1 = float(f1_score(human, pred, average="macro", zero_division=0))
    print(f"Trained on {len(train_rows)} rows (gold answers excluded); macro-F1 vs human labels = {f1:.2f}")
    print_report("Gold-set report", human, pred, class_report(human, pred))
    mlflow.log_dict(class_report(human, pred), "gold_report.json")
    return {"gold_kappa": kappa, "gold_f1_macro": f1, "gold_n": float(len(gold))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=config.STANCE_LABELS_FILE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--C", type=float, default=1.0)
    parser.add_argument("--class-weight", choices=["balanced", "none"], default="balanced")
    parser.add_argument("--no-mask", action="store_true", help="skip brand masking (ablation)")
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()
    args.class_weight = None if args.class_weight == "none" else args.class_weight

    rows = load_rows(args.labels)
    texts = [r["text"] for r in rows]
    y_true = [r["label"] for r in rows]
    groups = [r["response_id"] for r in rows]

    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(f"{config.STANCE_EXPERIMENT}-evaluation")
    with mlflow.start_run():
        mlflow.log_params(
            {"seed": args.seed, "C": args.C, "class_weight": str(args.class_weight), "folds": args.folds, "mask": not args.no_mask, "n": len(rows)}
        )
        y_pred = group_cv_predictions(
            texts, y_true, groups, seed=args.seed, C=args.C, class_weight=args.class_weight, n_splits=args.folds,
            mask=not args.no_mask,
        )
        f1, lo, hi = macro_f1_ci(y_true, y_pred, groups, seed=args.seed)
        base = majority_baseline(y_true)
        report = class_report(y_true, y_pred)

        print(f"{len(rows)} rows, {len(set(groups))} answers, {args.folds}-fold group CV")
        print(f"Model macro-F1 = {f1:.2f}  (95% CI {lo:.2f}-{hi:.2f})")
        print(f"Majority baseline: accuracy={base['accuracy']:.2f} macro-F1={base['f1_macro']:.2f}")
        print_report("Cross-validated report", y_true, y_pred, report)

        mlflow.log_metrics(
            {"cv_f1_macro": f1, "cv_f1_lower": lo, "cv_f1_upper": hi, "baseline_f1_macro": base["f1_macro"]}
        )
        mlflow.log_dict(report, "cv_report.json")
        mlflow.log_artifact(str(args.labels))
        gold_metrics = gold_evaluation(rows, args)
        if gold_metrics:
            mlflow.log_metrics(gold_metrics)


if __name__ == "__main__":
    main()

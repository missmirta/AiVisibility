"""Score the stance classifier on the human gold set over several seeds.

Run: uv run python scripts/gold_multiseed.py --features finetune --seeds 1 2 3 4 5 [--labels FILE]

One fine-tune run moves gold macro-F1 by about 9 points, so compare changes by the
seed mean. Gold answers are always removed from the training rows. No API calls.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, precision_recall_fscore_support

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.data import load_rows
from aivisibility.classifier.train import build_pipeline
from aivisibility.common import config

GOLD_FILE = config.STANCE_LABELS_FILE.with_name("gold.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=config.STANCE_LABELS_FILE)
    parser.add_argument("--features", choices=["tfidf", "embed", "finetune"], default="finetune")
    parser.add_argument("--extra", type=Path, nargs="*", default=[], help="more label CSVs added to training")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--epochs", type=int, help="finetune only: override epochs")
    parser.add_argument("--max-len", type=int, help="finetune only: override max token length")
    parser.add_argument("--model", help="finetune only: override the pretrained model name")
    args = parser.parse_args()
    tweaks = {"epochs": args.epochs, "max_len": args.max_len, "model_name": args.model}
    tweaks = {f"clf__{k}": v for k, v in tweaks.items() if v is not None}

    gold = [r for r in load_rows(GOLD_FILE) if r["human_label"]]
    human = [r["human_label"] for r in gold]
    gold_ids = {r["response_id"] for r in gold}
    gold_texts = {r["text"] for r in gold}
    # drop gold answers, and any identical snippet that sits in another answer
    all_rows = [r for path in [args.labels, *args.extra] for r in load_rows(path)]
    rows = [r for r in all_rows if r["response_id"] not in gold_ids and r["text"] not in gold_texts]
    labels = config.STANCE_LABELS
    print(f"{len(rows)} training rows (gold excluded), {len(gold)} gold rows, features={args.features}")

    f1s, neg_recalls, neg_precisions = [], [], []
    confusion = np.zeros((len(labels), len(labels)), dtype=int)
    for seed in args.seeds:
        pipe = build_pipeline(seed, class_weight="balanced", features=args.features)
        pipe.set_params(**tweaks)
        pipe.fit([r["text"] for r in rows], [r["label"] for r in rows])
        pred = pipe.predict([r["text"] for r in gold]).tolist()
        p, r, _, _ = precision_recall_fscore_support(human, pred, labels=labels, zero_division=0)
        i = labels.index("negative")
        f1s.append(f1_score(human, pred, average="macro", zero_division=0))
        neg_recalls.append(r[i])
        neg_precisions.append(p[i])
        for t, q in zip(human, pred):
            confusion[labels.index(t), labels.index(q)] += 1
        print(f"seed {seed}: gold macro-F1={f1s[-1]:.2f} negative P={p[i]:.2f} R={r[i]:.2f}", flush=True)

    print(f"\nmean gold macro-F1 = {np.mean(f1s):.3f} +- {np.std(f1s):.3f} over {len(f1s)} seeds")
    print(f"mean negative recall = {np.mean(neg_recalls):.2f}, precision = {np.mean(neg_precisions):.2f}")
    print(f"confusion summed over seeds (rows=true, cols=pred, order={labels}):")
    for row in confusion.tolist():
        print(f"  {row}")


if __name__ == "__main__":
    main()

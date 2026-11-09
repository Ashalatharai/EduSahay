"""Evaluate the trained classifier on a held-out test split. Usage: python evaluate.py --data ../datasets/classifier"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.config import settings  # noqa: E402
from app.ml.classifier import LABELS, DocumentClassifier  # noqa: E402


def evaluate(test_dir, model_path=None):
    clf = DocumentClassifier(model_path or settings.classifier_path)
    y_true, y_pred = [], []
    for i, label in enumerate(LABELS):
        for p in sorted((Path(test_dir) / label).glob("*")):
            y_true.append(i); y_pred.append(LABELS.index(clf.predict(p.read_bytes())["label"]))
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=list(range(len(LABELS))), zero_division=0)
    return {
        "samples": len(y_true), "model_version": clf.version, "trained_on": clf.meta.get("dataset_type"),
        "accuracy": accuracy_score(y_true, y_pred),
        "per_class": {l: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i])} for i, l in enumerate(LABELS)},
        "macro": {"precision": float(p.mean()), "recall": float(r.mean()), "f1": float(f.mean())},
        "confusion_matrix": {"labels": LABELS, "rows_true_cols_pred": confusion_matrix(y_true, y_pred, labels=list(range(len(LABELS)))).tolist()},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="../datasets/classifier")
    a = ap.parse_args()
    data = Path(a.data)
    res = evaluate(data / "test")
    res["dataset"] = json.loads((data / "meta.json").read_text()) if (data / "meta.json").exists() else {}
    out = Path(__file__).resolve().parents[1] / "evaluation" / "reports"; out.mkdir(parents=True, exist_ok=True)
    path = out / f"classifier_{datetime.now():%Y%m%d_%H%M%S}.json"; path.write_text(json.dumps(res, indent=2))
    print(f"Test samples: {res['samples']}   dataset type: {res['trained_on']}   accuracy: {res['accuracy']:.3f}")
    for l, m in res["per_class"].items():
        print(f"  {l:8s} precision {m['precision']:.3f}  recall {m['recall']:.3f}  f1 {m['f1']:.3f}")
    print("confusion matrix (rows=true, cols=predicted):", res["confusion_matrix"]["labels"])
    for row in res["confusion_matrix"]["rows_true_cols_pred"]: print("  ", row)
    if res["trained_on"] == "synthetic": print("NOTE: synthetic test data. These numbers do not reflect accuracy on real documents.")
    print(f"Report saved to {path}")

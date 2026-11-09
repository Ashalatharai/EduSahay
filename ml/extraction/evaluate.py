"""Field extraction precision / recall / F1 on the test split.

Uses the dataset's own words and boxes as input, so this measures the LayoutLMv3 extractor on its own (not OCR errors).
Usage: python evaluate.py --data ../datasets/extraction
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.config import settings  # noqa: E402
from app.ml.extraction import build_fields, decode_spans  # noqa: E402
from app.ml.extraction_metrics import field_scores  # noqa: E402


def to_fields(doc_type, words, boxes, labels, confs):
    return {f.name: f.value for f in build_fields(doc_type, decode_spans(words, boxes, labels, confs), 0.0) if f.value is not None}


def evaluate(test_dir, extractor):
    test_dir = Path(test_dir); gold, pred = [], []
    for line in (test_dir / "annotations.jsonl").read_text().splitlines():
        rec = json.loads(line)
        image = cv2.imread(str(test_dir / rec["image"]))
        labels, confs = extractor.predict_words(image, rec["words"], rec["boxes"])
        gold.append(to_fields(rec["doc_type"], rec["words"], rec["boxes"], rec["labels"], [1.0] * len(rec["words"])))
        pred.append(to_fields(rec["doc_type"], rec["words"], rec["boxes"], labels, confs))
    return field_scores(gold, pred)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="../datasets/extraction")
    a = ap.parse_args()
    from app.ml.layout_extractor import LayoutExtractor

    ext = LayoutExtractor(settings.extractor_dir)
    res = evaluate(Path(a.data) / "test", ext)
    res["model"] = ext.meta
    out = Path(__file__).resolve().parents[1] / "evaluation" / "reports"; out.mkdir(parents=True, exist_ok=True)
    path = out / f"extraction_{datetime.now():%Y%m%d_%H%M%S}.json"; path.write_text(json.dumps(res, indent=2))
    m = res["micro"]; print(f"micro  precision {m['precision']:.3f}  recall {m['recall']:.3f}  f1 {m['f1']:.3f}")
    for k, v in res["per_field"].items(): print(f"  {k:24s} P {v['precision']:.3f}  R {v['recall']:.3f}  F1 {v['f1']:.3f}  (n={v['support']})")
    if ext.meta.get("dataset_type") != "real": print("NOTE: prototype model on synthetic data. These numbers do not reflect real-document accuracy.")
    print(f"Report saved to {path}")

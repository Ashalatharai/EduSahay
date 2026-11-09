"""OCR evaluation: Character Error Rate (CER) and Word Error Rate (WER) with PaddleOCR.

Reference text comes from the annotated synthetic dataset (ml/extraction/make_extraction_dataset.py), whose words are known.
Usage: python evaluate.py --data ../datasets/extraction      (needs paddleocr + paddlepaddle; downloads OCR models on first run)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.ml.ocr import OcrLine, reading_order, run_ocr  # noqa: E402
from app.ml.text_metrics import cer, wer  # noqa: E402


def page_text(lines):
    """Join OCR lines in reading order, one row of words per line of text."""
    text, last_y = [], None
    for l in reading_order(lines):
        y = sum(p[1] for p in l.box) / 4
        if last_y is not None and abs(y - last_y) > 0.6 * (max(p[1] for p in l.box) - min(p[1] for p in l.box)):
            text.append("\n")
        text.append(l.text); last_y = y
    return " ".join(text).replace(" \n ", "\n")


def evaluate(test_dir, engine=None, limit=None):
    test_dir = Path(test_dir); per, rows = {}, [json.loads(l) for l in (test_dir / "annotations.jsonl").read_text().splitlines()]
    for rec in rows[:limit]:
        ref_lines = [OcrLine(w, 1.0, [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]) for w, b in zip(rec["words"], rec["boxes"])]
        reference = " ".join(l.text for l in reading_order(ref_lines))
        res = run_ocr((test_dir / rec["image"]).read_bytes(), engine)
        hypothesis = " ".join(l.text for l in res["lines"])
        per.setdefault(rec["doc_type"], []).append((cer(reference, hypothesis), wer(reference, hypothesis)))
    allv = [x for v in per.values() for x in v]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return {"documents": len(allv), "cer": mean([c for c, _ in allv]), "wer": mean([w for _, w in allv]),
            "per_doc_type": {k: {"cer": mean([c for c, _ in v]), "wer": mean([w for _, w in v]), "documents": len(v)} for k, v in per.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="../datasets/extraction"); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    res = evaluate(Path(a.data) / "test", limit=a.limit)
    out = Path(__file__).resolve().parents[1] / "evaluation" / "reports"; out.mkdir(parents=True, exist_ok=True)
    path = out / f"ocr_{datetime.now():%Y%m%d_%H%M%S}.json"; path.write_text(json.dumps(res, indent=2))
    print(f"documents {res['documents']}   CER {res['cer']:.4f}   WER {res['wer']:.4f}")
    for k, v in res["per_doc_type"].items(): print(f"  {k:8s} CER {v['cer']:.4f}  WER {v['wer']:.4f}  (n={v['documents']})")
    print("NOTE: synthetic documents; these numbers do not reflect real-document accuracy.")
    print(f"Report saved to {path}")

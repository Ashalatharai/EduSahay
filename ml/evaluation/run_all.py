"""Run every evaluation that can run, and write one summary. Anything unavailable is reported as skipped, never invented.

Usage: python run_all.py [--classifier-data ../datasets/classifier] [--extraction-data ../datasets/extraction]
"""
import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "backend"))


def load(rel):
    spec = importlib.util.spec_from_file_location(rel.replace("/", "_"), HERE.parent / rel)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def attempt(fn):
    try:
        return {"status": "ok", "results": fn()}
    except Exception as e:  # missing model, missing library or missing data: say so
        return {"status": "skipped", "reason": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--classifier-data", default=str(HERE.parent / "datasets" / "classifier"))
    ap.add_argument("--extraction-data", default=str(HERE.parent / "datasets" / "extraction"))
    a = ap.parse_args()
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cnn_classifier": attempt(lambda: load("classifier/evaluate.py").evaluate(Path(a.classifier_data) / "test")),
        "ocr_paddleocr": attempt(lambda: load("ocr/evaluate.py").evaluate(Path(a.extraction_data) / "test")),
        "layoutlmv3_extraction": attempt(lambda: load("extraction/evaluate.py").evaluate(
            Path(a.extraction_data) / "test", __import__("app.ml.layout_extractor", fromlist=["x"]).get_extractor())),
    }
    out = HERE / "reports"; out.mkdir(exist_ok=True)
    path = out / f"summary_{datetime.now():%Y%m%d_%H%M%S}.json"; path.write_text(json.dumps(summary, indent=2, default=str))
    for k, v in summary.items():
        if isinstance(v, dict): print(f"{k:24s} {v['status']}" + (f"  ({v['reason']})" if v["status"] == "skipped" else ""))
    print(f"Summary saved to {path}")

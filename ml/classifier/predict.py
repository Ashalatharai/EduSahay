"""Classify one file. Usage: python predict.py path/to/file.png"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.ml.classifier import get_classifier  # noqa: E402

print(json.dumps(get_classifier().predict(Path(sys.argv[1]).read_bytes()), indent=2))

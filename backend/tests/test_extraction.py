import json
import sys
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.errors import ModelNotAvailable
from app.ml.extraction import build_fields, decode_spans, words_from_lines
from app.ml.extraction_metrics import field_scores
from app.ml.extraction_schema import LABELS, allowed_field
from app.models import ExtractedInformation
from app.services import extraction as extraction_service
from app.services import ocr as ocr_service
from test_ocr import FakeEngine, bar_page, encode

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "extraction"))
import make_extraction_dataset as gen  # noqa: E402


def test_decode_and_build_fields():
    words = ["NAME", "ANANYA", "RAO", "Maths", "88", "Science", "x", "REG", "123"]
    boxes = [[0, 0, 10, 10], [20, 0, 60, 10], [65, 0, 90, 10], [0, 100, 40, 110], [200, 102, 220, 112],
             [0, 140, 40, 150], [200, 300, 210, 310], [0, 200, 10, 210], [20, 200, 50, 210]]
    labels = ["O", "B-NAME", "I-NAME", "B-SUBJECT", "B-MARKS", "B-SUBJECT", "B-MARKS", "O", "B-REG_NO"]
    confs = [1, .9, .8, .95, .99, .9, .95, 1, .4]
    spans = decode_spans(words, boxes, labels, confs)
    assert [(s.entity, s.text) for s in spans][:2] == [("NAME", "ANANYA RAO"), ("SUBJECT", "Maths")]
    f = {x.name: x for x in build_fields("sslc", spans, 0.7)}
    assert f["student_name"].value == "ANANYA RAO" and not f["student_name"].needs_review
    assert f["register_number"].value == "123" and f["register_number"].needs_review  # low confidence
    assert f["school_name"].value is None and f["school_name"].needs_review          # missing
    assert (f["subject_1_name"].value, f["subject_1_marks"].value) == ("Maths", "88")
    assert f["subject_2_marks"].value is None and f["subject_2_marks"].needs_review  # no marks on that row


def test_words_from_lines():
    w, b = words_from_lines([{"text": "AB CDEF", "box": [[0, 0], [90, 0], [90, 20], [0, 20]]}])
    assert w == ["AB", "CDEF"] and b[0][0] == 0 and b[1][0] > b[0][2] and b[1][2] <= 90


def test_field_scores():
    gold = [{"a": "x", "b": "y", "subject_1_name": "Maths"}, {"a": "z"}]
    pred = [{"a": "X", "b": "wrong", "subject_1_name": "Maths"}, {}]
    s = field_scores(gold, pred)
    assert s["per_field"]["a"] == {"precision": 1.0, "recall": 0.5, "f1": pytest.approx(2 / 3), "support": 2}
    assert s["per_field"]["b"]["precision"] == 0 and s["per_field"]["subject"]["f1"] == 1.0
    assert s["micro"]["precision"] == pytest.approx(2 / 3)


def test_annotated_dataset_is_consistent(tmp_path):
    gen.generate(tmp_path, {"train": 6}, seed=5)
    recs = [json.loads(l) for l in (tmp_path / "train" / "annotations.jsonl").read_text().splitlines()]
    assert len(recs) == 18 and {r["doc_type"] for r in recs} == {"aadhaar", "sslc", "puc"}
    for r in recs:
        n = len(r["words"])
        assert n == len(r["boxes"]) == len(r["labels"]) > 5
        assert (tmp_path / "train" / r["image"]).exists()
        prev = "O"
        for l, (x0, y0, x1, y1) in zip(r["labels"], r["boxes"]):
            assert l in LABELS and 0 <= x0 <= x1 < r["width"] and 0 <= y0 <= y1 < r["height"]
            if l.startswith("I-"):
                assert prev[2:] == l[2:]  # an I- tag continues the same entity
            prev = l
        # decoding the gold labels must give back exactly the values the generator drew
        spans = decode_spans(r["words"], r["boxes"], r["labels"], [1.0] * n)
        got = {f.name: f.value for f in build_fields(r["doc_type"], spans, 0.0) if f.value is not None}
        assert got == r["fields"], r["image"]


class FakeExtractor:
    def predict_words(self, image, words, boxes):
        table = {"ANANYA": ("B-NAME", .95), "RAO": ("I-NAME", .95), "1234567": ("B-REG_NO", .5)}
        out = [table.get(w, ("O", 1.0)) for w in words]
        return [o[0] for o in out], [o[1] for o in out]


def test_extraction_api(client, make_user, monkeypatch):
    class Engine(FakeEngine):
        def recognise(self, img):
            lines = super().recognise(img)
            if lines:
                lines[2].text = "NAME ANANYA RAO"
            return lines

    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_service, "get_engine", lambda: Engine())
    monkeypatch.setattr(extraction_service, "extractor_available", lambda: True)
    monkeypatch.setattr(extraction_service, "get_model", lambda: FakeExtractor())
    monkeypatch.setattr(extraction_service, "extractor_info",
                        lambda: {"dataset_type": "synthetic", "trained_at": None, "prototype": True})
    h, other = make_user("ext@example.com"), make_user("ext2@example.com")
    up = lambda: client.post("/api/documents/sslc", files={"file": ("a.png", encode(bar_page(True)))}, headers=h)

    doc = up().json()
    assert client.get("/api/documents", headers=h).json()[0]["status"] == "extracted"
    r = client.get(f"/api/documents/{doc['id']}/fields", headers=h).json()
    assert r["model"]["prototype"] is True
    f = {x["field_name"]: x for x in r["fields"]}
    assert f["student_name"]["value"] == "ANANYA RAO" and not f["student_name"]["needs_review"]
    assert f["register_number"]["needs_review"] and f["school_name"]["value"] is None
    assert client.get(f"/api/documents/{doc['id']}/fields", headers=other).status_code == 404

    # manual correction
    url = f"/api/documents/{doc['id']}/fields/register_number"
    c = client.put(url, json={"value": " 7654321 "}, headers=h).json()
    assert c["value"] == "7654321" and c["original_value"] == "1234567" and not c["needs_review"] and c["source"] == "manual"
    assert client.put(url, json={"value": "1"}, headers=other).status_code == 404
    assert client.put(f"/api/documents/{doc['id']}/fields/aadhaar_number_masked", json={"value": "1"}, headers=h).status_code == 404
    assert client.put(f"/api/documents/{doc['id']}/fields/student_name", json={"value": "123456789012"}, headers=h).json()["value"] == "XXXX XXXX 9012"

    # extractor unavailable
    def unavailable():
        raise ModelNotAvailable("not fine-tuned")

    monkeypatch.setattr(extraction_service, "get_model", unavailable)
    assert client.post(f"/api/documents/{doc['id']}/extract", headers=h).status_code == 503

    # replacing the document removes its extracted fields
    monkeypatch.setattr(extraction_service, "get_model", lambda: FakeExtractor())
    new = up().json()
    with SessionLocal() as db:
        ids = {r.document_id for r in db.query(ExtractedInformation)}
    assert new["id"] in ids and doc["id"] not in ids
    assert allowed_field("sslc", "subject_3_marks") and not allowed_field("aadhaar", "subject_1_name")

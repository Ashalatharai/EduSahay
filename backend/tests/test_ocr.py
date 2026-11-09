import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.errors import ModelNotAvailable
from app.ml.ocr import OcrLine, reading_order, run_ocr
from app.ml.ocr_preprocess import estimate_skew, prepare_for_ocr
from app.models import OcrResult
from app.services import ocr as ocr_service

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "classifier"))
import make_synthetic_dataset as gen  # noqa: E402


def sample_png(seed=1, kind=gen.sslc):
    pil = kind(random.Random(seed)).convert("L")
    return np.array(pil)


def encode(img):
    return cv2.imencode(".png", img)[1].tobytes()


class FakeEngine:
    name, version = "fake", "0"

    def recognise(self, img):
        if img[:40].mean() > 100:  # pretend text is only readable when the dark bar is on top
            return []
        box = lambda y: [[10, y], [200, y], [200, y + 20], [10, y + 20]]
        return [OcrLine("REGISTER NO 1234567", 0.97, box(30)), OcrLine("Aadhaar 1234 5678 9012", 0.95, box(70)),
                OcrLine("NAME ANANYA RAO", 0.99, box(110))]


def bar_page(bar_at_bottom=True):
    page = np.full((1000, 800), 255, np.uint8)
    page[-120:] = 0 if bar_at_bottom else page[-120:]
    if not bar_at_bottom:
        page[:120] = 0
    return page


def test_deskew_and_prepare():
    img = sample_png()
    h, w = img.shape
    rotated = cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), 3.0, 1), (w, h), borderValue=255)
    assert abs(estimate_skew(rotated) + 3.0) <= 1.0  # rotating by about -3 degrees straightens it
    assert estimate_skew(img) == 0.0
    out = prepare_for_ocr(encode(rotated))
    assert out.ndim == 3 and out.shape[2] == 3 and 1200 <= max(out.shape[:2]) <= 2200
    assert (prepare_for_ocr(encode(rotated)) == out).all()  # deterministic

    import fitz

    pdf = fitz.open(); pdf.new_page().insert_text((72, 72), "hello")
    assert prepare_for_ocr(pdf.tobytes()).shape[2] == 3


def test_rotated_page_is_retried():
    res = run_ocr(encode(bar_page(bar_at_bottom=True)), FakeEngine())
    assert res["rotation"] == 180 and len(res["lines"]) == 3
    res0 = run_ocr(encode(bar_page(bar_at_bottom=False)), FakeEngine())
    assert res0["rotation"] == 0


def test_reading_order():
    mk = lambda t, x, y: OcrLine(t, 0.9, [[x, y], [x + 50, y], [x + 50, y + 20], [x, y + 20]])
    ordered = reading_order([mk("c", 200, 100), mk("b", 120, 52), mk("a", 10, 50), mk("d", 10, 200)])
    assert [l.text for l in ordered] == ["a", "b", "c", "d"]


def test_mask_aadhaar():
    m = ocr_service.mask_aadhaar
    assert m("Aadhaar 1234 5678 9012 ok") == "Aadhaar XXXX XXXX 9012 ok"
    assert m("123456789012") == "XXXX XXXX 9012" and m("1234-5678-9012") == "XXXX XXXX 9012"
    assert m("Register 1234567") == "Register 1234567" and m("1234567890123") == "1234567890123"


def test_ocr_api(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_service, "get_engine", lambda: FakeEngine())
    h, other = make_user("ocr@example.com"), make_user("ocr2@example.com")
    up = lambda name, data: client.post("/api/documents/sslc", files={"file": (name, data)}, headers=h)

    # engine sees the dark bar at the bottom, so the page is rotated 180 degrees and read
    r = up("scan.png", encode(bar_page(True)))
    assert r.status_code == 201 and r.json()["status"] == "ocr_queued"
    doc_id = r.json()["id"]
    assert client.get("/api/documents", headers=h).json()[0]["status"] == "ocr_done"

    res = client.get(f"/api/documents/{doc_id}/ocr", headers=h)
    assert res.status_code == 200 and res.json()["rotation"] == 180 and len(res.json()["lines"]) == 3
    assert "XXXX XXXX 9012" in res.text and "5678" not in res.text  # masked before storage
    assert client.get(f"/api/documents/{doc_id}/ocr").status_code == 401
    assert client.get(f"/api/documents/{doc_id}/ocr", headers=other).status_code == 404

    # re-run endpoint, and engine-unavailable handling
    assert client.post(f"/api/documents/{doc_id}/ocr", headers=h).status_code == 200

    def unavailable():
        raise ModelNotAvailable("PaddleOCR is not installed")

    monkeypatch.setattr(ocr_service, "get_engine", unavailable)
    assert client.post(f"/api/documents/{doc_id}/ocr", headers=h).status_code == 503

    monkeypatch.setattr(ocr_service, "get_engine", lambda: FakeEngine())

    # unreadable file
    bad = up("bad.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40).json()
    assert client.get("/api/documents", headers=h).json()[0]["status"] == "unreadable"  # set by the background task

    # replacing the document removes the old OCR text
    new = up("scan2.png", encode(bar_page(True))).json()
    with SessionLocal() as db:
        ids = {r.document_id for r in db.query(OcrResult)}
    assert new["id"] in ids and doc_id not in ids and bad["id"] not in ids

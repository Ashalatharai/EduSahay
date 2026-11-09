import sys
from pathlib import Path

import pytest

from app.core.config import settings

ML = Path(__file__).resolve().parents[2] / "ml" / "classifier"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def up(c, h, slot, name, data):
    return c.post(f"/api/documents/{slot}", files={"file": (name, data)}, headers=h)


def test_without_a_trained_model(client, make_user):
    """Uploads keep working and the classify endpoint reports clearly that no model exists."""
    h = make_user("nomodel@example.com")
    r = up(client, h, "aadhaar", "a.png", PNG_BYTES)
    assert r.status_code == 201 and r.json()["classification"] is None and r.json()["status"] == "uploaded"
    assert client.post(f"/api/documents/{r.json()['id']}/classify", headers=h).status_code == 503


def test_train_evaluate_and_classify(client, make_user, tmp_path):
    """Smoke test of the real pipeline: generate data, train, evaluate, run inference through the API."""
    pytest.importorskip("torch")
    sys.path.insert(0, str(ML))
    import evaluate, make_synthetic_dataset as gen, train
    from app.ml.classifier import LABELS, get_classifier

    data = tmp_path / "data"
    gen.generate(data, {"train": 24, "val": 8, "test": 8}, seed=3)
    train.train(data, settings.classifier_path, epochs=12, batch=8)
    get_classifier.cache_clear()

    res = evaluate.evaluate(data / "test")
    assert res["samples"] == 32 and res["accuracy"] > 0.5  # chance is 0.25
    assert len(res["confusion_matrix"]["rows_true_cols_pred"]) == 4

    h = make_user("clf@example.com")
    sample = (data / "test" / "puc" / "0000.png").read_bytes()
    a = up(client, h, "aadhaar", "aadhaar_card.png", sample).json()
    b = up(client, h, "sslc", "totally_different_name.png", sample).json()
    assert a["classification"]["predicted_label"] in LABELS
    assert 0 <= a["classification"]["confidence"] <= 1
    # classification uses file content only, never the filename
    assert a["classification"]["predicted_label"] == b["classification"]["predicted_label"]
    assert a["classification"]["confidence"] == pytest.approx(b["classification"]["confidence"])

    bad = up(client, h, "puc", "x.jpg", b"\xff\xd8\xff" + b"junk" * 10).json()
    assert bad["status"] == "unreadable" and bad["classification"] is None

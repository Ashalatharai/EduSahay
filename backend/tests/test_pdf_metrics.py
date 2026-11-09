import fitz
import pytest

from app.db.session import SessionLocal
from app.ml.text_metrics import cer, edit_distance, wer
from app.models import AdmissionApplication, ExtractedInformation, UploadedDocument, User
from test_admin import login_admin


def test_cer_wer():
    assert edit_distance("kitten", "sitting") == 3
    assert cer("hello world", "hello world") == 0 and cer("abcd", "abxd") == 0.25
    assert wer("the quick brown fox", "the quick brown fox") == 0
    assert wer("the quick brown fox", "the quack brown") == 0.5
    assert cer("", "") == 0


def test_profile_pdf(client, make_user):
    h = make_user("pdf@example.com")
    sslc = client.post("/api/documents/sslc", files={"file": ("sslc.png", b"\x89PNG\r\n\x1a\n" + b"0" * 30)}, headers=h).json()["id"]
    assert client.get("/api/applications/me/profile.pdf", headers=h).status_code == 409  # not submitted yet
    with SessionLocal() as db:
        db.get(UploadedDocument, sslc).status = "extracted"
        db.add_all([ExtractedInformation(document_id=sslc, field_name="subject_1_name", value="Mathematics"),
                    ExtractedInformation(document_id=sslc, field_name="subject_1_marks", value="97")])
        user = db.query(User).filter_by(email="pdf@example.com").one()
        app = db.query(AdmissionApplication).filter_by(user_id=user.id).one()
        app.status = "submitted"
        app.form_data = {"final": {"full_name": "ANANYA RAO", "date_of_birth": "14/06/2008", "sslc_register_number": "1234567",
                                   "sslc_percentage": "91.5%", "email": "pdf@example.com"}}
        db.commit(); app_id = app.id
    r = client.get("/api/applications/me/profile.pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and "inline" in r.headers["content-disposition"]
    text = "".join(p.get_text() for p in fitz.open(stream=r.content, filetype="pdf"))
    for expected in ["Edu Sahaya", "ANANYA RAO", "1234567", "SSLC marks summary", "Mathematics", "97", "sslc.png", "Submitted", "Generated on"]:
        assert expected in text, expected
    assert "attachment" in client.get("/api/applications/me/profile.pdf?download=true", headers=h).headers["content-disposition"]
    assert client.get("/api/applications/me/profile.pdf").status_code == 401
    assert client.get(f"/api/admin/applications/{app_id}/profile.pdf", headers=make_user("pdf2@example.com")).status_code == 403
    assert client.get(f"/api/admin/applications/{app_id}/profile.pdf", headers=login_admin(client)).content.startswith(b"%PDF")

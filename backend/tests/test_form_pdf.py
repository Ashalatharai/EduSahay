import fitz

from app.db.session import SessionLocal
from app.models import AdmissionApplication, ExtractedInformation, UploadedDocument, User, ValidationResult
from app.services import ocr as ocr_service
from test_form import PNG


def _upload_and_extract(client, h, with_contact=False):
    ids = {s: client.post(f"/api/documents/{s}", files={"file": (f"{s}.png", PNG)}, headers=h).json()["id"] for s in ("aadhaar", "sslc", "puc")}
    data = {"aadhaar": {"student_name": "ANANYA RAO", "date_of_birth": "14/06/2008", "gender": "Female"},
            "sslc": {"register_number": "1234567", "school_name": "Sample High School", "exam_year": "2024", "percentage": "91.5%",
                     "subject_1_name": "Mathematics", "subject_1_marks": "97"},
            "puc": {"register_number": "87654321", "college_name": "Sample PU College", "exam_year": "2026", "percentage": "83.3 %"}}
    with SessionLocal() as db:
        for slot, vals in data.items():
            db.get(UploadedDocument, ids[slot]).status = "extracted"
            for k, v in vals.items():
                db.add(ExtractedInformation(document_id=ids[slot], field_name=k, value=v, confidence=0.99))
        db.commit()
    return ids


def _text(content):
    return "".join(p.get_text() for p in fitz.open(stream=content, filetype="pdf"))


def test_form_reports_missing_and_incorrect_fields(client, make_user):
    h = make_user("formerr@example.com")
    _upload_and_extract(client, h)
    f = {x["key"]: x for x in client.get("/api/applications/me/form", headers=h).json()["fields"]}
    assert f["full_name"]["value"] == "ANANYA RAO" and f["full_name"]["error"] is None  # filled from the document
    assert f["contact_number"]["error"] == "Contact number is required"  # missing
    saved = client.put("/api/applications/me/form", json={"values": {"contact_number": "123"}}, headers=h).json()
    assert {x["key"]: x for x in saved["fields"]}["contact_number"]["error"] == "Enter a 10-digit mobile number"  # incorrect


def test_admission_form_pdf_draft_then_submitted(client, make_user):
    h = make_user("formpdf@example.com")
    _upload_and_extract(client, h)
    client.put("/api/applications/me/form", json={"values": {"contact_number": "123"}}, headers=h)

    r = client.get("/api/applications/me/form.pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and "inline" in r.headers["content-disposition"]
    text = _text(r.content)
    for expected in ["ADMISSION FORM", "ANANYA RAO", "Sample High School", "87654321", "Mathematics", "97",
                     "Draft, not yet submitted", "Details to check before submitting", "Enter a 10-digit mobile number"]:
        assert expected in text, expected
    assert "attachment" in client.get("/api/applications/me/form.pdf?download=true", headers=h).headers["content-disposition"]
    assert client.get("/api/applications/me/form.pdf").status_code == 401

    client.put("/api/applications/me/form", json={"values": {"contact_number": "9876543210", "address": "12 Main Road"}}, headers=h)
    assert client.post("/api/applications/me/submit", json={"confirm": True}, headers=h).status_code == 200
    text = _text(client.get("/api/applications/me/form.pdf", headers=h).content)
    for expected in ["9876543210", "12 Main Road", "Submitted", "Confirmed by the student online on"]:
        assert expected in text, expected
    assert "Details to check" not in text


def test_checks_run_automatically_once_all_documents_are_processed(client, make_user):
    h = make_user("autochecks@example.com")
    _upload_and_extract(client, h)
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="autochecks@example.com").one()
        app = db.query(AdmissionApplication).filter_by(user_id=user.id).one()
        assert db.query(ValidationResult).filter_by(application_id=app.id).count() == 0
        ocr_service.refresh_checks(db, user.id)
        db.refresh(app)
        assert db.query(ValidationResult).filter_by(application_id=app.id).count() > 0
        assert app.status == "review_required"

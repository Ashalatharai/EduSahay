from app.db.session import SessionLocal
from app.models import ExtractedInformation, UploadedDocument
from app.services.form import validate_values

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 30
VALID = {"full_name": "A R", "date_of_birth": "14/06/2008", "gender": "Female", "contact_number": "9876543210",
         "email": "a@b.co", "address": "Somewhere", "sslc_register_number": "1", "sslc_school_name": "S", "sslc_exam_year": "2024",
         "sslc_percentage": "91.5%", "puc_register_number": "2", "puc_college_name": "C", "puc_exam_year": "2026", "puc_percentage": "83.3 %"}


def test_validate_values():
    assert validate_values(VALID) == {}
    bad = validate_values({**VALID, "contact_number": "123", "email": "nope", "date_of_birth": "32/01/2008",
                           "sslc_exam_year": "24", "puc_percentage": "140", "address": ""})
    assert set(bad) == {"contact_number", "email", "date_of_birth", "sslc_exam_year", "puc_percentage", "address"}
    assert validate_values({**VALID, "contact_number": "+91 98765-43210"}) == {}


def test_form_flow(client, make_user):
    h = make_user("form@example.com")
    ids = {s: client.post(f"/api/documents/{s}", files={"file": ("a.png", PNG)}, headers=h).json()["id"] for s in ("aadhaar", "sslc", "puc")}
    with SessionLocal() as db:
        for slot, vals in {"aadhaar": {"student_name": "ANANYA RAO", "date_of_birth": "14/06/2008", "gender": "Female"},
                           "sslc": {"register_number": "1234567", "school_name": "Sample High School", "exam_year": "2024", "percentage": "91.5%"},
                           "puc": {"register_number": "87654321", "college_name": "Sample PU College", "exam_year": "2026", "percentage": "83.3 %"}}.items():
            db.get(UploadedDocument, ids[slot]).status = "extracted"
            for k, v in vals.items():
                db.add(ExtractedInformation(document_id=ids[slot], field_name=k, value=v, confidence=0.99, needs_review=(k == "school_name")))
        db.commit()

    form = client.get("/api/applications/me/form", headers=h).json()
    f = {x["key"]: x for x in form["fields"]}
    assert form["editable"] and f["full_name"]["value"] == "ANANYA RAO" and f["full_name"]["source"] == "documents"
    assert f["email"]["value"] == "form@example.com" and f["email"]["source"] == "account"
    assert f["sslc_school_name"]["needs_review"] and not f["sslc_register_number"]["needs_review"]
    assert f["contact_number"]["value"] is None and f["contact_number"]["source"] == "manual"

    # submit is blocked until mandatory fields are valid and confirmed
    assert client.post("/api/applications/me/submit", json={"confirm": True}, headers=h).status_code == 422
    assert client.put("/api/applications/me/form", json={"values": {"bogus": "x"}}, headers=h).status_code == 422
    saved = client.put("/api/applications/me/form", json={"values": {"contact_number": "9876543210", "address": "12 Main Road"}}, headers=h).json()
    assert {x["key"]: x["value"] for x in saved["fields"]}["contact_number"] == "9876543210"
    assert client.post("/api/applications/me/submit", json={"confirm": False}, headers=h).status_code == 422
    r = client.post("/api/applications/me/submit", json={"confirm": True}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "submitted"

    # locked after submission
    assert client.put("/api/applications/me/form", json={"values": {"address": "x"}}, headers=h).status_code == 409
    assert client.delete(f"/api/documents/{ids['puc']}", headers=h).status_code == 409
    assert client.post("/api/applications/me/submit", json={"confirm": True}, headers=h).status_code == 409
    assert client.get("/api/applications/me/form", headers=h).json()["editable"] is False


def test_submit_needs_all_documents(client, make_user):
    h = make_user("form2@example.com")
    client.post("/api/documents/aadhaar", files={"file": ("a.png", PNG)}, headers=h)
    r = client.post("/api/applications/me/submit", json={"confirm": True}, headers=h)
    assert r.status_code == 422 and "sslc" in r.json()["detail"]

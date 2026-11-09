import io
import fitz
import pytest
from app.db.session import SessionLocal
from app.models import AdmissionApplication, ExtractedInformation, UploadedDocument, User
from app.services import form_filler


def create_sample_blank_pdf() -> bytes:
    """Creates a sample blank college admission form PDF with tables and underlines."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Header
    page.insert_text(fitz.Point(150, 50), "GOVERNMENT ENGINEERING COLLEGE", fontsize=16, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(170, 75), "APPLICATION FOR ADMISSION 2026-27", fontsize=12, fontname="helv", color=(0.2, 0.2, 0.2))

    # Personal Section
    page.insert_text(fitz.Point(50, 120), "1. Full Name: ___________________________________", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(50, 150), "2. Date of Birth: ________________  Gender: [ ] Male  [ ] Female", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(50, 180), "3. Aadhaar No: __________________  Contact No: _________________", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(50, 210), "4. Email Address: _________________________________", fontsize=10, fontname="helv")
    page.insert_text(fitz.Point(50, 240), "5. Permanent Address: _____________________________", fontsize=10, fontname="helv")

    # Academic Section
    page.insert_text(fitz.Point(50, 290), "ACADEMIC RECORD", fontsize=11, fontname="helv")
    page.draw_rect(fitz.Rect(50, 305, 545, 395), color=(0.5, 0.5, 0.5), width=0.8)
    page.draw_line(fitz.Point(50, 335), fitz.Point(545, 335), color=(0.5, 0.5, 0.5), width=0.8)
    page.draw_line(fitz.Point(50, 365), fitz.Point(545, 365), color=(0.5, 0.5, 0.5), width=0.8)

    # Columns
    page.insert_text(fitz.Point(55, 325), "Exam", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(130, 325), "Reg No", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(230, 325), "School / College", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(380, 325), "Year", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(440, 325), "Marks", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(500, 325), "%", fontsize=9, fontname="helv")

    # Rows
    page.insert_text(fitz.Point(55, 355), "SSLC", fontsize=9, fontname="helv")
    page.insert_text(fitz.Point(55, 385), "PUC", fontsize=9, fontname="helv")

    out = doc.tobytes()
    doc.close()
    return out


def test_parse_blank_form():
    pdf_bytes = create_sample_blank_pdf()
    fields = form_filler.parse_admission_form(pdf_bytes, "application/pdf")
    matched_keys = {f.matched_key for f in fields if f.matched_key}

    assert "full_name" in matched_keys
    assert "date_of_birth" in matched_keys
    assert "contact_number" in matched_keys
    assert "email" in matched_keys
    assert "address" in matched_keys


def test_auto_form_filler_api_flow(client, make_user):
    h = make_user("autofill@example.com")
    blank_pdf = create_sample_blank_pdf()

    # 1. Upload blank admission form
    r_form = client.post("/api/documents/admission_form", files={"file": ("blank_form.pdf", blank_pdf, "application/pdf")}, headers=h)
    assert r_form.status_code == 201
    form_doc_id = r_form.json()["id"]

    # 2. Upload supporting documents
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    doc_ids = {}
    for slot in ("aadhaar", "sslc", "puc"):
        doc_ids[slot] = client.post(f"/api/documents/{slot}", files={"file": (f"{slot}.png", png, "image/png")}, headers=h).json()["id"]

    # Populate extracted details in DB
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="autofill@example.com").one()
        user.full_name = "ANANYA RAO"
        db.get(UploadedDocument, doc_ids["aadhaar"]).status = "extracted"
        db.add(ExtractedInformation(document_id=doc_ids["aadhaar"], field_name="student_name", value="ANANYA RAO", confidence=0.99))
        db.add(ExtractedInformation(document_id=doc_ids["aadhaar"], field_name="date_of_birth", value="14/06/2008", confidence=0.98))
        db.add(ExtractedInformation(document_id=doc_ids["aadhaar"], field_name="gender", value="Female", confidence=0.97))
        db.add(ExtractedInformation(document_id=doc_ids["aadhaar"], field_name="aadhaar_number_masked", value="XXXX XXXX 1234", confidence=0.99))

        db.get(UploadedDocument, doc_ids["sslc"]).status = "extracted"
        db.add(ExtractedInformation(document_id=doc_ids["sslc"], field_name="register_number", value="SSLC12345", confidence=0.95))
        db.add(ExtractedInformation(document_id=doc_ids["sslc"], field_name="school_name", value="NATIONAL HIGH SCHOOL", confidence=0.92))
        db.add(ExtractedInformation(document_id=doc_ids["sslc"], field_name="percentage", value="92.5", confidence=0.96))

        db.get(UploadedDocument, doc_ids["puc"]).status = "extracted"
        db.add(ExtractedInformation(document_id=doc_ids["puc"], field_name="register_number", value="PUC67890", confidence=0.94))
        db.add(ExtractedInformation(document_id=doc_ids["puc"], field_name="college_name", value="ST JOSEPH COLLEGE", confidence=0.91))
        db.add(ExtractedInformation(document_id=doc_ids["puc"], field_name="percentage", value="94.2", confidence=0.95))

        # Fill profile
        user.profile.phone = "9876543210"
        user.profile.address = "12 Main Street, Bangalore"
        db.commit()

        # Run auto-filler
        form_filler.check_and_fill_admission_form(db, user.id)

    # 3. GET auto-form details
    r_get = client.get("/api/applications/me/auto-form", headers=h)
    assert r_get.status_code == 200
    data = r_get.json()
    assert data["status"] == "ready"
    assert data["pages_count"] >= 1
    fields_by_key = {f["matched_key"]: f["value"] for f in data["fields"] if f.get("matched_key")}

    assert fields_by_key.get("full_name") == "ANANYA RAO"
    assert fields_by_key.get("date_of_birth") == "14/06/2008"
    assert fields_by_key.get("contact_number") == "9876543210"
    assert fields_by_key.get("address") == "12 Main Street, Bangalore"

    # 4. Review & edit: student updates a field
    target_field = next(f for f in data["fields"] if f.get("matched_key") == "address")
    r_edit = client.put("/api/applications/me/auto-form", json={"edits": {target_field["field_id"]: "Flat 4B, Palm Grove, Bangalore"}}, headers=h)
    assert r_edit.status_code == 200
    updated_fields = {f["field_id"]: f["value"] for f in r_edit.json()["fields"]}
    assert updated_fields[target_field["field_id"]] == "Flat 4B, Palm Grove, Bangalore"

    # 5. Preview image endpoint
    r_prev = client.get("/api/applications/me/auto-form/preview/0", headers=h)
    assert r_prev.status_code == 200
    assert r_prev.headers["content-type"] == "image/png"
    assert len(r_prev.content) > 100

    # 6. Download completed filled PDF
    r_dl = client.get("/api/applications/me/auto-form/download", headers=h)
    assert r_dl.status_code == 200
    assert r_dl.headers["content-type"] == "application/pdf"
    assert "attachment" in r_dl.headers["content-disposition"]
    assert len(r_dl.content) > 1000

    # Verify that the downloaded PDF contains the auto-filled student text!
    with fitz.open(stream=r_dl.content, filetype="pdf") as filled_doc:
        text_content = filled_doc[0].get_text()
        assert "ANANYA RAO" in text_content
        assert "Flat 4B, Palm Grove, Bangalore" in text_content
        assert "GOVERNMENT ENGINEERING COLLEGE" in text_content  # Original header preserved!


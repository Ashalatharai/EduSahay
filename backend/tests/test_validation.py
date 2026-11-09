from app.db.session import SessionLocal
from app.models import ExtractedInformation, UploadedDocument
from app.services.validation import compare_dates, compare_names, run_checks

OK = "extracted"


def f(**kw):
    return {k: (v, False) for k, v in kw.items()}


def by_field(rows):
    return {r[0]: r[1] for r in rows}


def test_name_and_date_comparison():
    assert compare_names("Ananya K Rao", "RAO ANANYA") == "matched"
    assert compare_names("ANANYA RAO", "ANANYAA RAO") == "needs_review"
    assert compare_names("ANANYA RAO", "ROHAN SHETTY") == "mismatch"
    assert compare_dates("14/06/2008", "14-06-2008") == "matched"
    assert compare_dates("14/06/2008", "15/06/2008") == "mismatch"
    assert compare_dates("14/06/2008", "unclear") == "needs_review"


def test_all_consistent():
    docs = {"aadhaar": OK, "sslc": OK, "puc": OK}
    fields = {
        "aadhaar": f(student_name="ANANYA RAO", date_of_birth="14/06/2008", gender="Female", aadhaar_number_masked="XXXX XXXX 1234"),
        "sslc": f(student_name="Rao Ananya", date_of_birth="14-06-2008", register_number="1", school_name="S", exam_year="2024",
                  total_marks="150", percentage="91.5%", subject_1_marks="100", subject_2_marks="50"),
        "puc": f(student_name="ANANYA RAO", register_number="2", college_name="C", exam_year="2026", total_marks="500", percentage="83.3 %",
                 subject_1_marks="300", subject_2_marks="200"),
    }
    r = by_field(run_checks(docs, fields))
    assert r == {"student_name": "matched", "date_of_birth": "matched", "sslc.marks_total": "matched", "puc.marks_total": "matched"}


def test_problems_are_reported():
    docs = {"aadhaar": OK, "sslc": OK}  # PUC not uploaded
    fields = {
        "aadhaar": {**f(student_name="ANANYA RAO", date_of_birth="14/06/2008", gender="Female"), "aadhaar_number_masked": ("123456789012", False)},
        "sslc": {**f(student_name="ROHAN SHETTY", date_of_birth="15/06/2008", register_number="1", exam_year="2024", total_marks="150",
                     percentage="190", subject_1_marks="100", subject_2_marks="40"), "school_name": ("S", True)},
    }
    r = by_field(run_checks(docs, fields))
    assert r["document:puc"] == "missing"
    assert r["student_name"] == "mismatch" and r["date_of_birth"] == "mismatch"
    assert r["sslc.marks_total"] == "mismatch" and r["sslc.percentage"] == "needs_review"
    assert r["sslc.school_name"] == "needs_review" and r["aadhaar.aadhaar_number_masked"] == "needs_review"
    # mismatches are listed first
    assert list(by_field(run_checks(docs, fields)).values())[0] == "mismatch"


def test_missing_and_low_confidence_names():
    docs = {"aadhaar": OK, "sslc": OK, "puc": OK}
    fields = {"aadhaar": f(student_name="ANANYA RAO"), "sslc": {"student_name": ("ANANYA RAO", True)}, "puc": f(student_name="ANANYA RAO")}
    r = by_field(run_checks(docs, fields))
    assert r["student_name"] == "needs_review"  # agrees, but one source was read with low confidence
    assert r["date_of_birth"] == "missing"


def test_validation_api(client, make_user):
    h = make_user("val@example.com")
    assert client.get("/api/applications/me/validation", headers=h).json()["results"] == []
    PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 30
    ids = {}
    for slot in ("aadhaar", "sslc", "puc"):
        ids[slot] = client.post(f"/api/documents/{slot}", files={"file": ("a.png", PNG)}, headers=h).json()["id"]
    assert client.get("/api/applications/me", headers=h).json()["status"] == "documents_uploaded"
    with SessionLocal() as db:  # pretend processing finished and these fields were extracted
        for slot, vals in {"aadhaar": {"student_name": "ANANYA RAO", "date_of_birth": "14/06/2008"},
                           "sslc": {"student_name": "ANANYA RAO", "date_of_birth": "14/06/2008"},
                           "puc": {"student_name": "ANANYA RAO"}}.items():
            db.get(UploadedDocument, ids[slot]).status = "extracted"
            for k, v in vals.items():
                db.add(ExtractedInformation(document_id=ids[slot], field_name=k, value=v, confidence=0.99, needs_review=False))
        db.commit()
    out = client.post("/api/applications/me/validate", headers=h).json()
    st = {r["field_name"]: r["status"] for r in out["results"]}
    assert st["student_name"] == "matched" and st["date_of_birth"] == "matched"
    assert out["summary"]["matched"] == 2 and out["summary"]["missing"] > 0
    assert "not Aadhaar authentication" in out["disclaimer"]
    assert client.get("/api/applications/me", headers=h).json()["status"] == "review_required"
    assert client.get("/api/applications/me/validation", headers=h).json()["summary"] == out["summary"]
    assert client.post("/api/applications/me/validate").status_code == 401

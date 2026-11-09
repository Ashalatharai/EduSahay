"""Consolidates extracted details into the admission form, and validates and submits it."""
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdmissionApplication, ExtractedInformation, User, ValidationResult
from app.services.applications import SUPPORTING_SLOTS, active_documents, current_application
from app.services.validation import parse_date

# key, label, section, required, document sources in priority order [(slot, field)]
FORM_FIELDS = [
    ("full_name", "Full name", "personal", True, [("aadhaar", "student_name"), ("sslc", "student_name"), ("puc", "student_name")]),
    ("date_of_birth", "Date of birth", "personal", True, [("aadhaar", "date_of_birth"), ("sslc", "date_of_birth")]),
    ("gender", "Gender", "personal", True, [("aadhaar", "gender")]),
    ("contact_number", "Contact number", "personal", True, []),
    ("email", "Email address", "personal", True, []),
    ("address", "Address", "personal", True, []),
    ("sslc_register_number", "SSLC register number", "academic", True, [("sslc", "register_number")]),
    ("sslc_school_name", "SSLC school name", "academic", True, [("sslc", "school_name")]),
    ("sslc_exam_year", "SSLC examination year", "academic", True, [("sslc", "exam_year")]),
    ("sslc_total_marks", "SSLC total marks", "academic", False, [("sslc", "total_marks")]),
    ("sslc_percentage", "SSLC percentage", "academic", True, [("sslc", "percentage")]),
    ("puc_register_number", "PUC register number", "academic", True, [("puc", "register_number")]),
    ("puc_college_name", "PUC college name", "academic", True, [("puc", "college_name")]),
    ("puc_exam_year", "PUC examination year", "academic", True, [("puc", "exam_year")]),
    ("puc_total_marks", "PUC total marks", "academic", False, [("puc", "total_marks")]),
    ("puc_percentage", "PUC percentage", "academic", True, [("puc", "percentage")]),
]
KEYS = {f[0] for f in FORM_FIELDS}
CROSS_CHECKED = {"full_name": "student_name", "date_of_birth": "date_of_birth"}
EDITABLE_STATUSES = ("documents_not_uploaded", "documents_uploaded", "processing", "review_required", "correction_requested")


def _edits(app) -> dict:
    return (app.form_data or {}).get("edits", {})


def build_form(db: Session, user: User) -> dict:
    app = current_application(db, user)
    docs = {d.slot: d for d in active_documents(db, user)}
    rows = {}
    for slot, d in docs.items():
        for r in db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == d.id)):
            rows[(slot, r.field_name)] = r
    flagged = {v.field_name for v in db.scalars(select(ValidationResult).where(ValidationResult.application_id == app.id))
               if v.status in ("mismatch", "needs_review")}
    edits, out = _edits(app), []
    for key, label, section, required, sources in FORM_FIELDS:
        value, source, review = None, "manual", False
        for slot, name in sources:
            r = rows.get((slot, name))
            if r and r.current_value:
                value, source, review = r.current_value, "documents", r.needs_review
                break
        if key == "email":
            value, source = user.email, "account"
        if key == "full_name" and value is None:
            value, source = user.full_name, "account"
        if key in CROSS_CHECKED and CROSS_CHECKED[key] in flagged:
            review = True
        if key in edits:
            value, source, review = edits[key], "edited", False
        elif sources and value is None:
            review = True
        out.append({"key": key, "label": label, "section": section, "required": required,
                    "value": value, "source": source, "needs_review": review})
    errors = validate_values({f["key"]: f["value"] for f in out})  # missing or incorrect values, shown next to the field
    for f in out:
        f["error"] = errors.get(f["key"])
    return {"status": app.status, "editable": app.status in EDITABLE_STATUSES, "fields": out}


def validate_values(values: dict) -> dict:
    """Returns {field_key: message}; empty means valid."""
    err = {}
    for key, label, _, required, _ in FORM_FIELDS:
        v = (values.get(key) or "").strip()
        if not v:
            if required:
                err[key] = f"{label} is required"
            continue
        if key == "contact_number" and not re.fullmatch(r"[6-9]\d{9}", re.sub(r"[\s-]", "", v).removeprefix("+91")):
            err[key] = "Enter a 10-digit mobile number"
        elif key == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            err[key] = "Enter a valid email address"
        elif key == "date_of_birth" and parse_date(v) is None:
            err[key] = "Use the format DD/MM/YYYY"
        elif key.endswith("exam_year") and not re.fullmatch(r"(19|20)\d{2}", v):
            err[key] = "Enter a 4-digit year"
        elif key.endswith("percentage"):
            try:
                if not 0 <= float(v.replace("%", "").strip()) <= 100:
                    raise ValueError
            except ValueError:
                err[key] = "Enter a percentage between 0 and 100"
        elif key.endswith("total_marks") and not v.isdigit():
            err[key] = "Enter a whole number"
    return err


def save_edits(db: Session, user: User, values: dict) -> dict:
    app = current_application(db, user)
    unknown = set(values) - KEYS
    if unknown:
        raise KeyError(", ".join(sorted(unknown)))
    edits = {**_edits(app), **{k: (v or "").strip()[:500] for k, v in values.items()}}
    app.form_data = {**(app.form_data or {}), "edits": edits}
    db.commit()
    return build_form(db, user)


def submit(db: Session, user: User) -> AdmissionApplication:
    app = current_application(db, user)
    values = {f["key"]: f["value"] for f in build_form(db, user)["fields"]}
    app.form_data = {**(app.form_data or {}), "final": values}
    app.status, app.submitted_at = "submitted", datetime.now(timezone.utc)
    db.commit()
    return app


def missing_documents(db: Session, user: User) -> list[str]:
    have = {d.slot for d in active_documents(db, user)}
    return [s for s in SUPPORTING_SLOTS if s not in have]

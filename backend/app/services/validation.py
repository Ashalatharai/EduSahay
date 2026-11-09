"""Preliminary cross-document consistency checks. NOT Aadhaar authentication or government verification."""
import re
from datetime import date
from difflib import SequenceMatcher

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ml.extraction_schema import SINGLE_FIELDS
from app.models import AdmissionApplication, ExtractedInformation, User, ValidationResult
from app.services.applications import SUPPORTING_SLOTS, active_documents, current_application

DISCLAIMER = ("These are preliminary consistency checks between your own documents. They are not Aadhaar "
              "authentication or verification by any government authority.")
PROCESSED = {"ocr_done", "extracting", "extracted", "extraction_failed"}
CROSS = {"student_name": ("aadhaar", "sslc", "puc"), "date_of_birth": ("aadhaar", "sslc")}
ORDER = {"mismatch": 0, "missing": 1, "needs_review": 2, "matched": 3}


def _name_tokens(v: str) -> list[str]:
    return sorted(re.sub(r"[^A-Z ]", " ", v.upper()).split())


def compare_names(a: str, b: str) -> str:
    ta, tb = _name_tokens(a), _name_tokens(b)
    if {t for t in ta if len(t) > 1} == {t for t in tb if len(t) > 1}:
        return "matched"  # same names; initials may differ
    ratio = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    return "needs_review" if ratio >= 0.8 else "mismatch"  # close spelling variants are for a person to judge


def parse_date(v: str) -> date | None:
    m = re.fullmatch(r"\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\s*", v)
    try:
        return date(int(m[3]), int(m[2]), int(m[1])) if m else None
    except ValueError:
        return None


def compare_dates(a: str, b: str) -> str:
    da, db_ = parse_date(a), parse_date(b)
    if da is None or db_ is None:
        return "needs_review"
    return "matched" if da == db_ else "mismatch"


def _worst(statuses):
    return min(statuses, key=ORDER.get)


def run_checks(docs: dict, fields: dict) -> list[tuple[str, str, str]]:
    """docs: slot -> document status; fields: slot -> {name: (value, needs_review)}. Returns (field, status, detail)."""
    rows = []
    ready = {}
    for slot in SUPPORTING_SLOTS:
        if slot not in docs:
            rows.append((f"document:{slot}", "missing", "This document has not been uploaded"))
        elif docs[slot] not in PROCESSED:
            rows.append((f"document:{slot}", "needs_review", "This document could not be processed. Replace it with a clearer copy"))
        else:
            ready[slot] = fields.get(slot, {})

    def val(slot, name):
        v = ready.get(slot, {}).get(name)
        return v if v and v[0] else None

    for name, slots in CROSS.items():
        present = {s: val(s, name) for s in slots if s in ready and val(s, name)}
        absent = [s for s in slots if s in ready and s not in present]
        if not present:
            if ready:
                rows.append((name, "missing", "Not found in any processed document"))
            continue
        status, detail = "matched", f"Agrees across {', '.join(present)}"
        if len(present) > 1:
            cmp = compare_names if name == "student_name" else compare_dates
            pairs = [(a, b) for i, a in enumerate(present) for b in list(present)[i + 1:]]
            results = [(cmp(present[a][0], present[b][0]), a, b) for a, b in pairs]
            status = _worst([r[0] for r in results])
            bad = [f"{a} vs {b}" for st, a, b in results if st != "matched"]
            detail = f"Differs between {'; '.join(bad)}" if bad else detail
        if any(v[1] for v in present.values()) and status == "matched":
            status, detail = "needs_review", "Read with low confidence. Please check the value"
        if absent and status == "matched":
            status, detail = "missing", f"Not found in {', '.join(absent)} ({detail.lower()})"
        elif len(present) == 1 and status == "matched":
            status, detail = "missing", f"Only found in {next(iter(present))}, so it cannot be compared"
        rows.append((name, status, detail))

    for slot, f in ready.items():
        for name in SINGLE_FIELDS[slot].values():
            if name in CROSS:
                continue
            v = f.get(name)
            if not v or not v[0]:
                rows.append((f"{slot}.{name}", "missing", f"{name.replace('_', ' ').capitalize()} was not found"))
            elif v[1]:
                rows.append((f"{slot}.{name}", "needs_review", "Read with low confidence. Please check the value"))
        if slot in ("sslc", "puc"):
            marks = [int(x[0]) for k, x in f.items() if re.fullmatch(r"subject_\d+_marks", k) and x[0] and x[0].strip().isdigit()]
            total = f.get("total_marks")
            if marks and total and total[0] and total[0].strip().isdigit():
                ok = sum(marks) == int(total[0])
                rows.append((f"{slot}.marks_total", "matched" if ok else "mismatch",
                             "Subject marks add up to the total" if ok else f"Subject marks add up to {sum(marks)}, but the total reads {total[0]}"))
            pct = f.get("percentage")
            if pct and pct[0]:
                try:
                    if not 0 <= float(pct[0].replace("%", "").strip()) <= 100:
                        rows.append((f"{slot}.percentage", "needs_review", "Percentage is outside 0 to 100"))
                except ValueError:
                    rows.append((f"{slot}.percentage", "needs_review", "Percentage is not a number"))
    num = val("aadhaar", "aadhaar_number_masked")
    if num and not re.fullmatch(r"XXXX XXXX \d{4}", num[0].strip()):
        rows.append(("aadhaar.aadhaar_number_masked", "needs_review", "Expected a masked number like XXXX XXXX 1234"))
    return sorted(rows, key=lambda r: (ORDER[r[1]], r[0]))


def collect(db: Session, user: User):
    docs = {d.slot: d for d in active_documents(db, user)}
    fields = {}
    for slot, d in docs.items():
        rows = db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == d.id)).all()
        fields[slot] = {r.field_name: (r.current_value, r.needs_review) for r in rows}
    return {s: d.status for s, d in docs.items()}, fields


def validate_application(db: Session, user: User) -> AdmissionApplication:
    app = current_application(db, user)
    rows = run_checks(*collect(db, user))
    db.execute(delete(ValidationResult).where(ValidationResult.application_id == app.id))
    for field, status, detail in rows:
        db.add(ValidationResult(application_id=app.id, field_name=field, status=status, detail=detail))
    if app.status in ("documents_uploaded", "processing", "review_required") and not any(r[0].startswith("document:") and r[1] == "missing" for r in rows):
        app.status = "review_required"
    db.commit()
    return app


def results_for(db: Session, app: AdmissionApplication) -> dict:
    rows = db.scalars(select(ValidationResult).where(ValidationResult.application_id == app.id)).all()
    rows = sorted(rows, key=lambda r: (ORDER[r.status], r.field_name))
    summary = {s: sum(1 for r in rows if r.status == s) for s in ORDER}
    return {"summary": summary, "disclaimer": DISCLAIMER,
            "results": [{"field_name": r.field_name, "status": r.status, "detail": r.detail} for r in rows]}

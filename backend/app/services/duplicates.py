"""Flags possibly duplicate applications for an administrator to review. Never rejects anything automatically."""
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdmissionApplication, DuplicateDetectionResult
from app.services.validation import parse_date

THRESHOLD = 0.75
COUNTED = ("submitted", "approved", "correction_requested")


def _norm(v) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9 ]", " ", (v or "").lower()).split()))


def similarity(a: dict, b: dict) -> tuple[float, list[str]]:
    reasons = []
    name = SequenceMatcher(None, _norm(a.get("full_name")), _norm(b.get("full_name"))).ratio()
    da, db_ = parse_date(a.get("date_of_birth") or ""), parse_date(b.get("date_of_birth") or "")
    dob = da is not None and da == db_
    same = lambda k: bool(_norm(a.get(k))) and _norm(a.get(k)) == _norm(b.get(k))
    sslc, puc = same("sslc_register_number"), same("puc_register_number")
    score = 0.45 * name + 0.25 * dob + 0.15 * sslc + 0.15 * puc
    if name >= 0.85: reasons.append(f"Similar name ({name:.0%})")
    if dob: reasons.append("Same date of birth")
    if sslc: reasons.append("Same SSLC register number")
    if puc: reasons.append("Same PUC register number")
    if sslc or puc:
        score = max(score, 0.9)  # identifiers rarely coincide by chance
    if name >= 0.9 and dob:
        score = max(score, 0.85)
    return round(score, 3), reasons


def final_values(app: AdmissionApplication) -> dict | None:
    return (app.form_data or {}).get("final")


def detect_duplicates(db: Session, app: AdmissionApplication) -> list[DuplicateDetectionResult]:
    mine = final_values(app)
    old = db.scalars(select(DuplicateDetectionResult).where(DuplicateDetectionResult.application_id == app.id)).all()
    reviewed = {o.matched_application_id for o in old if o.reviewed}
    for o in old:
        db.delete(o)
    found = []
    if mine:
        others = db.scalars(select(AdmissionApplication).where(
            AdmissionApplication.id != app.id, AdmissionApplication.user_id != app.user_id,
            AdmissionApplication.status.in_(COUNTED))).all()
        for other in others:
            theirs = final_values(other)
            if not theirs:
                continue
            score, reasons = similarity(mine, theirs)
            if score >= THRESHOLD:
                row = DuplicateDetectionResult(application_id=app.id, matched_application_id=other.id, similarity=score,
                                               reasons=reasons, reviewed=other.id in reviewed)
                db.add(row); found.append(row)
    db.commit()
    return found

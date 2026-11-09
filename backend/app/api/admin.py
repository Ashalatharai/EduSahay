from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models import (AdminReview, AdmissionApplication, DuplicateDetectionResult, ExtractedInformation, User)
from app.services import form as form_service
from app.services.applications import active_documents
from app.services.pdf import build_profile_pdf
from app.services.duplicates import detect_duplicates, final_values
from app.services.validation import results_for

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_role("admin")


class ReviewIn(BaseModel):
    decision: str  # approved | correction_requested
    comments: str | None = None


def _values(db, app):
    return final_values(app) or {**{f["key"]: f["value"] for f in form_service.build_form(db, app.user)["fields"]}}


def _app_or_404(db, app_id):
    app = db.get(AdmissionApplication, app_id)
    if not app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


@router.get("/stats")
def stats(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    count = lambda *where: db.scalar(select(func.count(AdmissionApplication.id)).where(*where))
    return {"total_applications": count(), "documents_uploaded": count(AdmissionApplication.status != "documents_not_uploaded"),
            "pending_review": count(AdmissionApplication.status == "submitted"),
            "needs_correction": count(AdmissionApplication.status == "correction_requested"),
            "approved": count(AdmissionApplication.status == "approved")}


@router.get("/applications")
def list_applications(q: str | None = None, status_filter: str | None = None, _: User = Depends(admin_only),
                      db: Session = Depends(get_db)):
    query = select(AdmissionApplication).order_by(AdmissionApplication.updated_at.desc()).limit(500)
    if status_filter:
        query = query.where(AdmissionApplication.status == status_filter)
    dup_counts = dict(db.execute(select(DuplicateDetectionResult.application_id, func.count()).group_by(DuplicateDetectionResult.application_id)).all())
    out = []
    for app in db.scalars(query):
        v = final_values(app) or (app.form_data or {}).get("edits", {})
        row = {"id": app.id, "student_name": v.get("full_name") or app.user.full_name, "email": app.user.email, "status": app.status,
               "submitted_at": app.submitted_at, "sslc_register_number": v.get("sslc_register_number"),
               "puc_register_number": v.get("puc_register_number"), "possible_duplicates": dup_counts.get(app.id, 0)}
        if q:
            hay = " ".join(str(row[k] or "") for k in ("student_name", "email", "sslc_register_number", "puc_register_number")).lower()
            if q.lower().strip() not in hay:
                continue
        out.append(row)
    return out


@router.get("/applications/{app_id}")
def application_detail(app_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = _app_or_404(db, app_id)
    docs = []
    for d in active_documents(db, app.user):
        fields = db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == d.id).order_by(ExtractedInformation.id)).all()
        c = d.classification
        docs.append({"id": d.id, "slot": d.slot, "original_name": d.original_name, "mime_type": d.mime_type, "status": d.status,
                     "classification": c and {"label": c.predicted_label, "confidence": c.confidence, "recognised": c.recognised},
                     "fields": [{"field_name": f.field_name, "value": f.current_value, "confidence": f.confidence,
                                 "needs_review": f.needs_review, "source": f.source} for f in fields]})
    labels = {k: label for k, label, *_ in form_service.FORM_FIELDS}
    dups = db.scalars(select(DuplicateDetectionResult).where(or_(DuplicateDetectionResult.application_id == app.id,
                                                                  DuplicateDetectionResult.matched_application_id == app.id))).all()
    dup_out = []
    for r in dups:
        other = db.get(AdmissionApplication, r.matched_application_id if r.application_id == app.id else r.application_id)
        dup_out.append({"id": r.id, "other_application_id": other.id, "other_student": (final_values(other) or {}).get("full_name") or other.user.full_name,
                        "similarity": r.similarity, "reasons": r.reasons or [], "reviewed": r.reviewed})
    reviews = db.scalars(select(AdminReview).where(AdminReview.application_id == app.id).order_by(AdminReview.id)).all()
    return {"id": app.id, "status": app.status, "student": {"name": app.user.full_name, "email": app.user.email},
            "created_at": app.created_at, "submitted_at": app.submitted_at, "documents": docs,
            "form": [{"key": k, "label": labels[k], "value": v} for k, v in _values(db, app).items()],
            "validation": results_for(db, app), "duplicates": dup_out,
            "history": [{"decision": r.decision, "comments": r.comments, "created_at": r.created_at,
                         "admin": db.get(User, r.admin_id).email} for r in reviews]}


@router.post("/applications/{app_id}/review")
def review(app_id: int, body: ReviewIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = _app_or_404(db, app_id)
    if body.decision not in ("approved", "correction_requested"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Decision must be 'approved' or 'correction_requested'")
    if app.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted applications can be reviewed")
    if body.decision == "correction_requested" and not (body.comments or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Say what the student needs to correct")
    db.add(AdminReview(application_id=app.id, admin_id=admin.id, decision=body.decision, comments=(body.comments or "").strip() or None))
    app.status = body.decision
    db.commit()
    return {"id": app.id, "status": app.status}


@router.post("/applications/{app_id}/detect-duplicates")
def rerun_duplicates(app_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"found": len(detect_duplicates(db, _app_or_404(db, app_id)))}


@router.post("/duplicates/{dup_id}/review")
def review_duplicate(dup_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    row = db.get(DuplicateDetectionResult, dup_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    row.reviewed = True
    db.commit()
    return {"id": row.id, "reviewed": True}


@router.get("/applications/{app_id}/profile.pdf")
def profile_pdf(app_id: int, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    return Response(build_profile_pdf(db, _app_or_404(db, app_id)), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="admission-profile.pdf"', "Cache-Control": "no-store"})

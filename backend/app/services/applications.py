from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdmissionApplication, UploadedDocument, User

SUPPORTING_SLOTS = ("aadhaar", "sslc", "puc")
FORM_SLOT = "admission_form"
SLOTS = ("aadhaar", "sslc", "puc", "admission_form")
LOCKED = ("submitted", "approved")


def current_application(db: Session, user: User) -> AdmissionApplication:
    return db.scalars(
        select(AdmissionApplication).where(AdmissionApplication.user_id == user.id).order_by(AdmissionApplication.id.desc())
    ).first()


def active_documents(db: Session, user: User) -> list[UploadedDocument]:
    return list(db.scalars(
        select(UploadedDocument).where(UploadedDocument.user_id == user.id, UploadedDocument.deleted_at.is_(None))
        .order_by(UploadedDocument.slot)
    ))


def sync_status(db: Session, user: User) -> None:
    """Move between 'not uploaded' and 'uploaded'; later phases own the other statuses."""
    app = current_application(db, user)
    if not app or app.status not in ("documents_not_uploaded", "documents_uploaded"):
        return
    slots = {d.slot for d in active_documents(db, user)}
    app.status = "documents_uploaded" if slots >= set(SUPPORTING_SLOTS) else "documents_not_uploaded"

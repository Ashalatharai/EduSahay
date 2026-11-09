import os
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.db.session import get_db
from app.models import ExtractedInformation, OcrResult, UploadedDocument, User
from app.schemas.documents import DocumentOut, FieldOut, FieldsOut, FieldUpdate, OcrResultOut
from app.ml.errors import ModelNotAvailable, UnreadableImage
from app.ml.extraction_schema import allowed_field
from app.services import extraction as extraction_service
from app.services import ocr as ocr_service
from app.services import storage
from app.services.classification import classify_document, get_model
from app.services.applications import LOCKED, SLOTS, active_documents, current_application, sync_status

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _ensure_editable(db: Session, user: User) -> None:
    if current_application(db, user).status in LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Documents cannot be changed after submission")


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    return active_documents(db, user)


@router.post("/{slot}", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload(slot: str, file: UploadFile, background: BackgroundTasks, user: User = Depends(require_role("student")),
                 db: Session = Depends(get_db)):
    if slot not in SLOTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown document type")
    if not user.consent_given_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Consent is required before uploading documents")
    _ensure_editable(db, user)

    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File is larger than {settings.max_upload_mb} MB")
    try:
        mime = storage.detect_type(file.filename or "", content)
    except storage.InvalidUpload as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    new_path = storage.save_encrypted(content)
    for old in (d for d in active_documents(db, user) if d.slot == slot):  # replace
        storage.delete_file(old.stored_path)
        ocr_service.purge_ocr(db, old.id)
        ocr_service.purge_fields(db, old.id)
        old.stored_path, old.deleted_at = "", datetime.now(timezone.utc)
    doc = UploadedDocument(user_id=user.id, slot=slot, original_name=os.path.basename(file.filename)[:255],
                           stored_path=new_path, mime_type=mime, size_bytes=len(content))
    db.add(doc)
    db.flush()
    sync_status(db, user)
    db.commit()
    await run_in_threadpool(classify_document, db, doc)
    if doc.status != "unreadable" and ocr_service.ocr_available():
        doc.status = "ocr_queued"
        db.commit()
        background.add_task(ocr_service.ocr_task, doc.id)
    if slot == "admission_form":
        from app.services.form_filler import bg_fill_admission_form
        background.add_task(bg_fill_admission_form, user.id)
    return doc


@router.post("/{doc_id}/classify", response_model=DocumentOut)
def classify(doc_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    doc = db.get(UploadedDocument, doc_id)
    if not doc or doc.deleted_at or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    try:
        get_model()
    except ModelNotAvailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    classify_document(db, doc)
    db.refresh(doc)
    return doc


def _owned_or_admin(db: Session, user: User, doc_id: int) -> UploadedDocument:
    doc = db.get(UploadedDocument, doc_id)
    if not doc or doc.deleted_at or (user.role != "admin" and doc.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("/{doc_id}/ocr", response_model=OcrResultOut)
def get_ocr(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _owned_or_admin(db, user, doc_id)
    row = db.scalar(select(OcrResult).where(OcrResult.document_id == doc.id))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No text has been read from this document yet")
    return row


@router.post("/{doc_id}/ocr", response_model=OcrResultOut)
def run_ocr_now(doc_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    doc = _owned_or_admin(db, user, doc_id)
    try:
        row = ocr_service.store_ocr(db, doc)
    except ModelNotAvailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except UnreadableImage as e:
        doc.status = "unreadable"
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    doc.status = "ocr_done"
    db.commit()
    return row


@router.get("/{doc_id}/fields", response_model=FieldsOut)
def get_fields(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _owned_or_admin(db, user, doc_id)
    rows = db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == doc.id)
                      .order_by(ExtractedInformation.id)).all()
    return {"model": extraction_service.extractor_info(), "fields": [
        {"field_name": r.field_name, "value": r.current_value, "original_value": r.value, "confidence": r.confidence,
         "needs_review": r.needs_review, "source": r.source} for r in rows]}


@router.post("/{doc_id}/extract", response_model=FieldsOut)
def extract_now(doc_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    doc = _owned_or_admin(db, user, doc_id)
    try:
        extraction_service.extract_document(db, doc)
    except ModelNotAvailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except extraction_service.NoOcrResult as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    doc.status = "extracted"
    db.commit()
    return get_fields(doc_id, user, db)


@router.put("/{doc_id}/fields/{field_name}", response_model=FieldOut)
def correct_field(doc_id: int, field_name: str, body: FieldUpdate, user: User = Depends(require_role("student")),
                  db: Session = Depends(get_db)):
    doc = _owned_or_admin(db, user, doc_id)
    if not allowed_field(doc.slot, field_name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown field")
    _ensure_editable(db, user)
    value = ocr_service.mask_aadhaar(body.value.strip())[:200]
    row = db.scalar(select(ExtractedInformation).where(ExtractedInformation.document_id == doc.id,
                                                       ExtractedInformation.field_name == field_name))
    if not row:
        row = ExtractedInformation(document_id=doc.id, field_name=field_name, source="manual")
        db.add(row)
    row.corrected_value, row.needs_review, row.source = value, False, "manual"
    db.commit()
    return {"field_name": row.field_name, "value": row.current_value, "original_value": row.value,
            "confidence": row.confidence, "needs_review": False, "source": "manual"}


@router.get("/{doc_id}/file")
def get_file(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(UploadedDocument, doc_id)
    if not doc or doc.deleted_at or (user.role != "admin" and doc.user_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return Response(storage.read_decrypted(doc.stored_path), media_type=doc.mime_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Content-Disposition": "inline"})


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(doc_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    doc = db.get(UploadedDocument, doc_id)
    if not doc or doc.deleted_at or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    _ensure_editable(db, user)
    storage.delete_file(doc.stored_path)
    ocr_service.purge_ocr(db, doc.id)
    ocr_service.purge_fields(db, doc.id)
    doc.stored_path, doc.deleted_at = "", datetime.now(timezone.utc)
    db.flush()
    sync_status(db, user)
    db.commit()

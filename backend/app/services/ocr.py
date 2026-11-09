"""Stores OCR results and runs OCR in the background. Aadhaar numbers are masked BEFORE anything is stored."""
import importlib.util
import logging
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.errors import ModelNotAvailable, UnreadableImage
from app.models import ExtractedInformation, OcrResult, UploadedDocument, User
from app.ml.ocr import get_engine, run_ocr
from app.services import storage

log = logging.getLogger(__name__)
_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?(\d{4})(?!\d)")


def mask_aadhaar(text: str) -> str:
    return _AADHAAR.sub(lambda m: f"XXXX XXXX {m.group(1)}", text)


def ocr_available() -> bool:
    return settings.ocr_enabled and (
        importlib.util.find_spec("paddleocr") is not None
        or importlib.util.find_spec("easyocr") is not None
    )


def purge_ocr(db: Session, document_id: int) -> None:
    db.execute(delete(OcrResult).where(OcrResult.document_id == document_id))


def purge_fields(db: Session, document_id: int) -> None:
    db.execute(delete(ExtractedInformation).where(ExtractedInformation.document_id == document_id))


def store_ocr(db: Session, doc: UploadedDocument, engine=None) -> OcrResult:
    res = run_ocr(storage.read_decrypted(doc.stored_path), engine or get_engine())
    purge_ocr(db, doc.id)
    row = OcrResult(
        document_id=doc.id, engine=res["engine"], engine_version=res["engine_version"], rotation=res["rotation"],
        image_width=res["image_width"], image_height=res["image_height"], mean_confidence=res["mean_confidence"],
        lines=[{"text": mask_aadhaar(l.text), "confidence": l.confidence, "box": l.box} for l in res["lines"]],
    )
    db.add(row)
    return row


def refresh_checks(db: Session, user_id: int) -> None:
    """When all three documents have been processed, run the cross-document checks so the form opens with them ready.
    Skipped once the application is submitted, so recorded checks are never overwritten."""
    from app.services.applications import LOCKED, SUPPORTING_SLOTS, active_documents, current_application
    from app.services.validation import PROCESSED, validate_application

    user = db.get(User, user_id)
    docs = active_documents(db, user)
    if current_application(db, user).status in LOCKED:
        return
    if {d.slot for d in docs} >= set(SUPPORTING_SLOTS) and all(d.status in PROCESSED for d in docs if d.slot in SUPPORTING_SLOTS):
        validate_application(db, user)


def ocr_task(doc_id: int) -> None:
    """Background task. Logs failure types only, never document content."""
    with SessionLocal() as db:
        doc = db.get(UploadedDocument, doc_id)
        if not doc or doc.deleted_at:
            return
        try:
            doc.status = "ocr_running"
            db.commit()
            store_ocr(db, doc)
            doc.status = "ocr_done"
        except UnreadableImage:
            doc.status = "unreadable"
        except ModelNotAvailable:
            doc.status = "ocr_failed"
        except Exception:
            log.exception("OCR failed for document %s", doc_id)
            doc.status = "ocr_failed"
        db.commit()
        if doc.status == "ocr_done":
            from app.services import extraction  # local import avoids a circular import

            if extraction.extractor_available():
                doc.status = "extracting"
                db.commit()
                try:
                    extraction.extract_document(db, doc)
                    doc.status = "extracted"
                except Exception:
                    log.exception("Extraction failed for document %s", doc_id)
                    doc.status = "extraction_failed"
                db.commit()
            try:
                from app.services.form_filler import check_and_fill_admission_form
                check_and_fill_admission_form(db, doc.user_id)
            except Exception:
                log.exception("Auto-form filling trigger failed for document %s", doc_id)
        try:
            refresh_checks(db, doc.user_id)
        except Exception:
            log.exception("Automatic checks failed for document %s", doc_id)

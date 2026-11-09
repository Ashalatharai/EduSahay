"""Runs the CNN on a stored document and records the result. Failures never break uploads."""
import logging

from sqlalchemy.orm import Session

from app.models import DocumentClassificationResult, UploadedDocument
from app.ml.errors import ModelNotAvailable, UnreadableImage
from app.services import storage

log = logging.getLogger(__name__)


def get_model():
    try:
        from app.ml.classifier import get_classifier
    except ImportError as e:  # PyTorch not installed
        raise ModelNotAvailable("PyTorch is not installed") from e
    return get_classifier()


def classify_document(db: Session, doc: UploadedDocument) -> None:
    if doc.slot == "admission_form":
        db.add(DocumentClassificationResult(document_id=doc.id, predicted_label="admission_form",
                                            confidence=1.0, model_version="form_detector_v1"))
        doc.status = "classified"
        db.commit()
        return
    try:
        model = get_model()
    except ModelNotAvailable:
        return  # document stays 'uploaded'; classify later once a model exists
    try:
        result = model.predict(storage.read_decrypted(doc.stored_path))
    except UnreadableImage:
        doc.status = "unreadable"
        db.commit()
        return
    except Exception:  # log the failure type only, never document content
        log.exception("Classification failed for document %s", doc.id)
        return
    db.add(DocumentClassificationResult(document_id=doc.id, predicted_label=result["label"],
                                        confidence=result["confidence"], model_version=model.version))
    doc.status = "classified"
    db.commit()

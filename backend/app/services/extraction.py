"""Runs LayoutLMv3 on stored OCR output and saves the extracted fields."""
import importlib.util
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.errors import ModelNotAvailable
from app.ml.extraction import build_fields, decode_spans, extract_fields_from_ocr, words_from_lines
from app.ml.ocr_preprocess import prepare_for_ocr
from app.models import ExtractedInformation, OcrResult, UploadedDocument
from app.services import storage
from app.services.ocr import mask_aadhaar


class NoOcrResult(RuntimeError):
    pass


def extractor_available() -> bool:
    return (Path(settings.extractor_dir) / "config.json").exists() and importlib.util.find_spec("transformers") is not None


def extractor_info() -> dict | None:
    meta = Path(settings.extractor_dir) / "extractor_meta.json"
    if not (Path(settings.extractor_dir) / "config.json").exists():
        return None
    data = json.loads(meta.read_text()) if meta.exists() else {}
    return {"dataset_type": data.get("dataset_type", "unknown"), "trained_at": data.get("trained_at"),
            "prototype": data.get("dataset_type", "unknown") != "real"}


def get_model():
    try:
        from app.ml.layout_extractor import get_extractor
    except ImportError as e:
        raise ModelNotAvailable("transformers/PyTorch are not installed") from e
    return get_extractor()


def extract_document(db: Session, doc: UploadedDocument, extractor=None) -> None:
    ocr = db.scalar(select(OcrResult).where(OcrResult.document_id == doc.id))
    if not ocr:
        raise NoOcrResult("Text must be read from the document first")
    if extractor is not None or extractor_available():
        extractor = extractor or get_model()
        image = prepare_for_ocr(storage.read_decrypted(doc.stored_path), ocr.rotation)  # same image the OCR boxes refer to
        words, boxes = words_from_lines(ocr.lines)
        labels, confs = extractor.predict_words(image, words, boxes)
        fields = build_fields(doc.slot, decode_spans(words, boxes, labels, confs), settings.extraction_min_confidence)
    else:
        fields = extract_fields_from_ocr(doc.slot, ocr.lines)
    db.execute(delete(ExtractedInformation).where(ExtractedInformation.document_id == doc.id))
    for f in fields:
        db.add(ExtractedInformation(document_id=doc.id, field_name=f.name, value=mask_aadhaar(f.value) if f.value else None,
                                    confidence=f.confidence, bbox=f.box, needs_review=f.needs_review, source="model"))

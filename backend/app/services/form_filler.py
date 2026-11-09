"""Automatic admission form filling engine.

Uses OCR and deep learning to understand the layout and fields of the student's uploaded blank
admission form, matches them to details extracted from Aadhaar, SSLC and PUC documents, and automatically
fills the original admission form with exact design, table, and alignment preservation.
"""
from datetime import datetime, timezone
import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AdmissionApplication,
    AutoFilledForm,
    ExtractedInformation,
    UploadedDocument,
    User,
)
from app.ml.form_parser import FormFieldItem, parse_admission_form
from app.services import storage
from app.services.applications import FORM_SLOT, SUPPORTING_SLOTS, active_documents, current_application

log = logging.getLogger(__name__)


def get_available_student_details(db: Session, user: User) -> dict[str, str]:
    """Consolidates all extracted info from supporting documents, profile, and existing form edits."""
    app = current_application(db, user)
    docs = {d.slot: d for d in active_documents(db, user)}
    details: dict[str, str] = {}

    # 1. Base user and profile
    if user.full_name:
        details["full_name"] = user.full_name
    if user.email:
        details["email"] = user.email
    if user.profile:
        p = user.profile
        if p.phone:
            details["contact_number"] = p.phone
        if p.address:
            details["address"] = p.address
        if p.gender:
            details["gender"] = p.gender
        if p.date_of_birth:
            details["date_of_birth"] = f"{p.date_of_birth.day:02d}/{p.date_of_birth.month:02d}/{p.date_of_birth.year}"

    # Default nationality
    details["nationality"] = "Indian"

    # 2. Extracted info from Aadhaar, SSLC, PUC
    for slot in SUPPORTING_SLOTS:
        doc = docs.get(slot)
        if not doc:
            continue
        for row in db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == doc.id)):
            val = (row.current_value or "").strip()
            if not val:
                continue
            if slot == "aadhaar":
                if row.field_name == "student_name" and ("full_name" not in details or details["full_name"] == user.full_name):
                    details["full_name"] = val
                elif row.field_name == "date_of_birth":
                    details["date_of_birth"] = val
                elif row.field_name == "gender":
                    details["gender"] = val
                elif row.field_name in ("aadhaar_number_masked", "aadhaar_number"):
                    details["aadhaar_number"] = val
            elif slot == "sslc":
                if row.field_name == "student_name" and "full_name" not in details:
                    details["full_name"] = val
                elif row.field_name == "date_of_birth" and "date_of_birth" not in details:
                    details["date_of_birth"] = val
                elif row.field_name == "register_number":
                    details["sslc_register_number"] = val
                elif row.field_name == "school_name":
                    details["sslc_school_name"] = val
                elif row.field_name == "exam_year":
                    details["sslc_exam_year"] = val
                elif row.field_name == "total_marks":
                    details["sslc_total_marks"] = val
                elif row.field_name == "percentage":
                    details["sslc_percentage"] = val
            elif slot == "puc":
                if row.field_name == "student_name" and "full_name" not in details:
                    details["full_name"] = val
                elif row.field_name == "register_number":
                    details["puc_register_number"] = val
                elif row.field_name == "college_name":
                    details["puc_college_name"] = val
                elif row.field_name == "exam_year":
                    details["puc_exam_year"] = val
                elif row.field_name == "total_marks":
                    details["puc_total_marks"] = val
                elif row.field_name == "percentage":
                    details["puc_percentage"] = val

    # 3. Form edits if student reviewed the standard form
    if app and app.form_data:
        edits = app.form_data.get("edits", {})
        for k, v in edits.items():
            if v and str(v).strip():
                details[k] = str(v).strip()

    return details


def get_or_create_auto_form(db: Session, app: AdmissionApplication, form_doc: UploadedDocument) -> AutoFilledForm:
    auto_form = db.scalar(select(AutoFilledForm).where(AutoFilledForm.application_id == app.id))
    if not auto_form:
        auto_form = AutoFilledForm(application_id=app.id, document_id=form_doc.id, status="pending")
        db.add(auto_form)
        db.flush()
    else:
        auto_form.document_id = form_doc.id
    return auto_form


def bg_fill_admission_form(user_id: int) -> None:
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        try:
            check_and_fill_admission_form(db, user_id)
        except Exception:
            log.exception("Background auto form fill failed for user %s", user_id)


def check_and_fill_admission_form(db: Session, user_id: int) -> AutoFilledForm | None:
    """Triggered after document uploads or OCR. Parses blank form and pre-fills student details."""
    user = db.get(User, user_id)
    if not user:
        return None
    app = current_application(db, user)
    if not app:
        return None

    form_doc = next((d for d in active_documents(db, user) if d.slot == FORM_SLOT), None)
    if not form_doc:
        return None

    auto_form = get_or_create_auto_form(db, app, form_doc)
    student_details = get_available_student_details(db, user)

    try:
        raw_bytes = storage.read_decrypted(form_doc.stored_path)
    except Exception as e:
        log.warning("Could not decrypt form document %s: %s", form_doc.id, e)
        auto_form.status = "error"
        db.commit()
        return auto_form

    auto_form.status = "processing"
    db.commit()

    try:
        fields = parse_admission_form(raw_bytes, form_doc.mime_type)
        existing_edits = auto_form.edits or {}

        # Fill matched student details
        for f in fields:
            val = None
            if f.matched_key == "gender_male":
                gender = student_details.get("gender", "").lower()
                val = "\u2713" if gender == "male" else ""
            elif f.matched_key == "gender_female":
                gender = student_details.get("gender", "").lower()
                val = "\u2713" if gender == "female" else ""
            elif f.matched_key:
                val = student_details.get(f.matched_key)

            f.suggested_value = val or ""
            f.user_value = existing_edits.get(f.field_id, f.suggested_value)

        # Generate filled PDF
        filled_bytes = render_filled_admission_form(raw_bytes, form_doc.mime_type, fields)

        # Store filled PDF encrypted
        if auto_form.stored_pdf_path:
            storage.delete_file(auto_form.stored_pdf_path)
        auto_form.stored_pdf_path = storage.save_encrypted(filled_bytes)
        auto_form.fields_data = [f.to_dict() for f in fields]
        auto_form.status = "ready"
        db.commit()
        return auto_form

    except Exception:
        log.exception("Failed to auto-fill admission form for user %s", user_id)
        auto_form.status = "error"
        db.commit()
        return auto_form


def render_filled_admission_form(original_bytes: bytes, mime_type: str, fields: list[FormFieldItem]) -> bytes:
    """Overlays values onto the original admission form document, preserving design, lines, and alignment."""
    if mime_type == "application/pdf" or original_bytes.startswith(b"%PDF"):
        return _render_filled_pdf(original_bytes, fields)
    return _render_filled_image(original_bytes, fields)


def _render_filled_pdf(pdf_bytes: bytes, fields: list[FormFieldItem]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Check for AcroForm widgets first
    has_acro = any(list(p.widgets()) for p in doc)
    if has_acro:
        field_map = {f.label: (f.user_value or f.suggested_value or "") for f in fields if f.field_type in ("acroform", "checkbox")}
        for page in doc:
            for w in page.widgets():
                name = w.field_name or ""
                if name in field_map and field_map[name]:
                    val = field_map[name]
                    if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                        w.field_value = (val.lower() in ("yes", "true", "1", "\u2713", "x"))
                    else:
                        w.field_value = str(val)
                    w.update()

    # Overlay flat text fields on top of pages
    fields_by_page: dict[int, list[FormFieldItem]] = {}
    for f in fields:
        if f.field_type != "acroform":
            fields_by_page.setdefault(f.page, []).append(f)

    for page_idx, page_fields in fields_by_page.items():
        if page_idx >= len(doc):
            continue
        page = doc[page_idx]

        for f in page_fields:
            val = (f.user_value if f.user_value is not None else f.suggested_value) or ""
            val = str(val).strip()
            if not val:
                continue  # Leave unavailable fields blank

            bx0, by0, bx1, by1 = f.input_bbox
            box_h = by1 - by0
            box_w = bx1 - bx0

            # Compute font size
            fontsize = max(8.5, min(10.5, box_h * 0.75 if box_h > 10 else 9.5))

            # Alignment coordinate
            if f.field_type == "checkbox":
                text_x = bx0 + max(1.0, (box_w - 6) / 2)
                text_y = by1 - 2.0
                fontsize = 11.0
            else:
                text_x = bx0 + 3.0
                text_y = by1 - 2.5

            try:
                page.insert_text(
                    fitz.Point(text_x, text_y),
                    val,
                    fontsize=fontsize,
                    fontname="helv",
                    color=(0.04, 0.12, 0.32),  # Professional deep navy pen ink
                )
            except Exception as e:
                log.warning("Could not insert text '%s' on page %s: %s", val, page_idx, e)

    out_bytes = doc.tobytes(deflate=True, garbage=3)
    doc.close()
    return out_bytes


def _render_filled_image(image_bytes: bytes, fields: list[FormFieldItem]) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    for f in fields:
        val = (f.user_value if f.user_value is not None else f.suggested_value) or ""
        val = str(val).strip()
        if not val:
            continue

        bx0, by0, bx1, by1 = f.input_bbox
        x = bx0 + 4
        y = by0 + 2

        draw.text((x, y), val, fill=(10, 35, 85), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def get_auto_form(db: Session, user: User) -> dict:
    """Returns the auto-filled form details and field values for student review."""
    app = current_application(db, user)
    form_doc = next((d for d in active_documents(db, user) if d.slot == FORM_SLOT), None)

    if not form_doc:
        return {
            "status": "no_form_uploaded",
            "message": "Upload your blank college admission form to enable automatic form filling.",
            "fields": [],
            "pages_count": 0,
            "document": None,
        }

    auto_form = db.scalar(select(AutoFilledForm).where(AutoFilledForm.application_id == app.id))
    if not auto_form or auto_form.status == "pending" or not auto_form.fields_data:
        # Trigger filling now if not yet completed
        auto_form = check_and_fill_admission_form(db, user.id)

    if not auto_form or auto_form.status != "ready":
        return {
            "status": auto_form.status if auto_form else "processing",
            "message": "Analyzing form layout and filling details...",
            "fields": [],
            "pages_count": 0,
            "document": {"id": form_doc.id, "original_name": form_doc.original_name, "mime_type": form_doc.mime_type},
        }

    fields = auto_form.fields_data or []
    edits = auto_form.edits or {}

    out_fields = []
    for f in fields:
        cur_val = edits.get(f["field_id"], f.get("user_value") or f.get("suggested_value") or "")
        out_fields.append({
            "field_id": f["field_id"],
            "label": f["label"],
            "section": f.get("section", "personal"),
            "page": f.get("page", 0),
            "matched_key": f.get("matched_key"),
            "value": cur_val,
            "suggested_value": f.get("suggested_value") or "",
            "confidence": f.get("confidence", 0.9),
            "field_type": f.get("field_type", "text"),
            "is_edited": f["field_id"] in edits,
        })

    # Count pages from PDF
    pages_count = 1
    if auto_form.stored_pdf_path:
        try:
            pdf_b = storage.read_decrypted(auto_form.stored_pdf_path)
            with fitz.open(stream=pdf_b, filetype="pdf") as d:
                pages_count = len(d)
        except Exception:
            pages_count = max([f.get("page", 0) for f in fields] + [0]) + 1

    return {
        "status": "ready",
        "document": {"id": form_doc.id, "original_name": form_doc.original_name, "mime_type": form_doc.mime_type},
        "fields": out_fields,
        "pages_count": pages_count,
        "updated_at": auto_form.updated_at.isoformat() if auto_form.updated_at else None,
    }


def save_auto_form_edits(db: Session, user: User, edits: dict[str, str]) -> dict:
    """Updates user-edited fields and re-renders the filled PDF with updated values."""
    app = current_application(db, user)
    form_doc = next((d for d in active_documents(db, user) if d.slot == FORM_SLOT), None)
    if not form_doc:
        raise ValueError("No admission form uploaded")

    auto_form = get_or_create_auto_form(db, app, form_doc)
    current_edits = dict(auto_form.edits or {})
    current_edits.update(edits)
    auto_form.edits = current_edits

    # Read original blank form
    raw_bytes = storage.read_decrypted(form_doc.stored_path)
    fields_data = auto_form.fields_data or []

    items = []
    for f in fields_data:
        val = current_edits.get(f["field_id"], f.get("suggested_value") or "")
        item = FormFieldItem(
            field_id=f["field_id"],
            page=f["page"],
            label=f["label"],
            label_bbox=f["label_bbox"],
            input_bbox=f["input_bbox"],
            field_type=f["field_type"],
            matched_key=f.get("matched_key"),
            section=f.get("section", "personal"),
            confidence=f.get("confidence", 0.9),
            suggested_value=f.get("suggested_value"),
            user_value=val,
        )
        items.append(item)

    filled_bytes = render_filled_admission_form(raw_bytes, form_doc.mime_type, items)

    if auto_form.stored_pdf_path:
        storage.delete_file(auto_form.stored_pdf_path)
    auto_form.stored_pdf_path = storage.save_encrypted(filled_bytes)
    auto_form.updated_at = datetime.now(timezone.utc)
    db.commit()

    return get_auto_form(db, user)


def get_auto_form_preview_image(db: Session, user: User, page_no: int = 0) -> bytes:
    """Renders page_no of the filled admission form as a PNG image for interactive browser preview."""
    app = current_application(db, user)
    auto_form = db.scalar(select(AutoFilledForm).where(AutoFilledForm.application_id == app.id))
    if not auto_form or not auto_form.stored_pdf_path:
        auto_form = check_and_fill_admission_form(db, user.id)

    if not auto_form or not auto_form.stored_pdf_path:
        raise FileNotFoundError("Filled form preview is not available yet")

    pdf_bytes = storage.read_decrypted(auto_form.stored_pdf_path)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if page_no >= len(doc):
            page_no = 0
        page = doc[page_no]
        pix = page.get_pixmap(dpi=150)
        return pix.tobytes("png")


def get_auto_form_pdf(db: Session, user: User) -> bytes:
    """Returns the completed filled admission form as a PDF byte stream."""
    app = current_application(db, user)
    auto_form = db.scalar(select(AutoFilledForm).where(AutoFilledForm.application_id == app.id))
    if not auto_form or not auto_form.stored_pdf_path:
        auto_form = check_and_fill_admission_form(db, user.id)

    if not auto_form or not auto_form.stored_pdf_path:
        raise FileNotFoundError("Filled admission form PDF is not ready")

    return storage.read_decrypted(auto_form.stored_pdf_path)

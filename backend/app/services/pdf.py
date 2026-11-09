"""Admission profile PDF (ReportLab)."""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdmissionApplication, ExtractedInformation
from app.services import form as form_service
from app.services.applications import active_documents
from app.services.duplicates import final_values

NAVY, TEAL, MIST, INK = colors.HexColor("#163B65"), colors.HexColor("#16A6A1"), colors.HexColor("#F4F7FA"), colors.HexColor("#263445")
DOC_NAMES = {"aadhaar": "Aadhaar card", "sslc": "SSLC marks card", "puc": "PUC marks card"}
DOC_STATUS = {"uploaded": "Uploaded", "classified": "Document type identified", "ocr_queued": "Waiting to be read", "ocr_running": "Reading text",
              "ocr_done": "Text read", "extracting": "Finding details", "extracted": "Details extracted", "unreadable": "Could not be read",
              "ocr_failed": "Text could not be read", "extraction_failed": "Details could not be extracted"}
APP_STATUS = {"documents_not_uploaded": "Documents not uploaded", "documents_uploaded": "Documents uploaded", "processing": "Processing",
              "review_required": "Review required", "submitted": "Submitted", "approved": "Approved", "correction_requested": "Correction requested"}


def _table(rows, widths, header=False):
    t = Table(rows, colWidths=widths)
    style = [("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, MIST]), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DDE6")),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def build_profile_pdf(db: Session, app: AdmissionApplication) -> bytes:
    user = app.user
    values = final_values(app) or {f["key"]: f["value"] for f in form_service.build_form(db, user)["fields"]}
    v = lambda k: values.get(k) or "-"
    docs = active_documents(db, user)
    subjects = {}
    for d in docs:
        rows = {r.field_name: r.current_value for r in db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == d.id))}
        subjects[d.slot] = [(rows.get(f"subject_{i}_name"), rows.get(f"subject_{i}_marks")) for i in range(1, 13) if rows.get(f"subject_{i}_name")]

    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading3"], textColor=NAVY, spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")
    small = ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#5B6B7C"))
    story = [Spacer(1, 4)]

    def header(canvas, doc):
        w, ht = A4
        canvas.setFillColor(NAVY); canvas.rect(0, ht - 28 * mm, w, 28 * mm, stroke=0, fill=1)
        canvas.setFillColor(TEAL); canvas.rect(0, ht - 29.5 * mm, w, 1.5 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold", 20); canvas.drawString(18 * mm, ht - 15 * mm, "Edu Sahaya")
        canvas.setFont("Helvetica", 9); canvas.drawString(18 * mm, ht - 21 * mm, "Simplifying Admissions Through Intelligent Document Processing")
        canvas.setFont("Helvetica-Bold", 12); canvas.drawRightString(w - 18 * mm, ht - 15 * mm, "ADMISSION PROFILE")
        canvas.setFillColor(colors.HexColor("#5B6B7C")); canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 10 * mm, "Generated from documents submitted by the student. Not an official record or government verification.")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")

    W = 174 * mm
    story += [Paragraph("Personal details", h), _table([[k, v(key)] for k, key in [
        ("Full name", "full_name"), ("Date of birth", "date_of_birth"), ("Gender", "gender"), ("Contact number", "contact_number"),
        ("Email address", "email"), ("Address", "address")]], [45 * mm, W - 45 * mm])]
    story += [Paragraph("Academic details", h), _table(
        [["", "SSLC", "PUC"], ["Register number", v("sslc_register_number"), v("puc_register_number")],
         ["School / college", v("sslc_school_name"), v("puc_college_name")], ["Examination year", v("sslc_exam_year"), v("puc_exam_year")],
         ["Total marks", v("sslc_total_marks"), v("puc_total_marks")], ["Percentage", v("sslc_percentage"), v("puc_percentage")]],
        [45 * mm, (W - 45 * mm) / 2, (W - 45 * mm) / 2], header=True)]
    for slot, title in (("sslc", "SSLC marks summary"), ("puc", "PUC marks summary")):
        rows = subjects.get(slot)
        story.append(Paragraph(title, h))
        story.append(_table([["Subject", "Marks"]] + [[n, m or "-"] for n, m in rows], [W - 35 * mm, 35 * mm], header=True)
                     if rows else Paragraph("Subject marks were not extracted from the uploaded document.", small))
    story += [Paragraph("Uploaded documents", h), _table(
        [["Document", "File", "Processing status"]] + [[DOC_NAMES[d.slot], d.original_name[:40], DOC_STATUS.get(d.status, d.status)] for d in docs],
        [45 * mm, W - 95 * mm, 50 * mm], header=True)]
    story += [Paragraph("Application status", h), _table([["Final status", APP_STATUS.get(app.status, app.status)],
                                                       ["Generated on", datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")]], [45 * mm, W - 45 * mm])]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, topMargin=36 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
                      title="Edu Sahaya Admission Profile", author="Edu Sahaya").build(story, onFirstPage=header, onLaterPages=header)
    return buf.getvalue()

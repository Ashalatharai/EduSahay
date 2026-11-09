"""Admission form PDF (ReportLab).

Every value comes from the form the student reviews, which is built from the extracted document fields plus the student's
own edits. Nothing is invented: a value that is not known prints as a dash and is listed under "Details to check".
"""
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdmissionApplication, ExtractedInformation
from app.services import form as form_service
from app.services.applications import LOCKED, active_documents
from app.services.duplicates import final_values
from app.services.pdf import APP_STATUS, INK, MIST, NAVY, TEAL

W = 174 * mm
AMBER_BG, AMBER_LINE, MUTED, GRID = colors.HexColor("#FFFBEB"), colors.HexColor("#FBBF24"), colors.HexColor("#5B6B7C"), colors.HexColor("#D5DDE6")
PERSONAL = [("Full name", "full_name"), ("Date of birth", "date_of_birth"), ("Gender", "gender"), ("Contact number", "contact_number"),
            ("Email address", "email")]
ACADEMIC = [("Register number", "register_number"), ("School / college", None), ("Examination year", "exam_year"),
            ("Total marks", "total_marks"), ("Percentage", "percentage")]
DECLARATION = ("I declare that the information given in this form is true and complete to the best of my knowledge and "
               "matches the documents I uploaded.")


def attention_items(fields: list[dict]) -> list[tuple[str, str]]:
    """(label, reason) for every field that is empty, invalid or read with low confidence."""
    out = []
    for f in fields:
        if f.get("error"):
            out.append((f["label"], f["error"]))
        elif f.get("needs_review"):
            out.append((f["label"], "Read with low confidence. Please check it against your document"))
    return out


def render_admission_form(values: dict, subjects: dict, *, application_no: str, status_label: str, submitted: bool,
                          confirmed_on: datetime | None, attention: list[tuple[str, str]]) -> bytes:
    v = lambda k: (values.get(k) or "").strip() or "-"
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading3"], textColor=NAVY, spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")
    label = ParagraphStyle("l", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, leading=11)
    value = ParagraphStyle("v", parent=ss["Normal"], fontSize=9.5, textColor=INK, leading=12, fontName="Helvetica-Bold")
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, textColor=INK, leading=12)
    small = ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=MUTED)
    head = ParagraphStyle("th", parent=ss["Normal"], fontSize=9, textColor=colors.white, fontName="Helvetica-Bold")
    P = lambda text, style: Paragraph(escape(str(text)), style)

    def grid(rows, widths, header=False):
        t = Table(rows, colWidths=widths)
        style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, GRID), ("TOPPADDING", (0, 0), (-1, -1), 5),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, MIST])]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
        t.setStyle(TableStyle(style))
        return t

    story = [Spacer(1, 2)]
    story += [P("A. Personal details", h), grid([[P(l, label), P(v(k), value)] for l, k in PERSONAL] +
                                                  [[P("Address", label), P(v("address"), value)]], [45 * mm, W - 45 * mm])]
    cols = [45 * mm, (W - 45 * mm) / 2, (W - 45 * mm) / 2]
    rows = [[P("", head), P("SSLC", head), P("PUC", head)]]
    for name, key in ACADEMIC:
        if key is None:
            rows.append([P("School / college", label), P(v("sslc_school_name"), value), P(v("puc_college_name"), value)])
        else:
            rows.append([P(name, label), P(v(f"sslc_{key}"), value), P(v(f"puc_{key}"), value)])
    story += [P("B. Academic details", h), grid(rows, cols, header=True)]

    for slot, title in (("sslc", "SSLC"), ("puc", "PUC")):
        subs = subjects.get(slot) or []
        block = [P(f"C. {title} subject marks" if slot == "sslc" else f"D. {title} subject marks", h)]
        block.append(grid([[P("Subject", head), P("Marks", head)]] + [[P(n, body), P(m or "-", body)] for n, m in subs], [W - 35 * mm, 35 * mm], header=True)
                     if subs else P("Subject marks were not extracted from the uploaded document.", small))
        story.append(KeepTogether(block))

    if attention and not submitted:
        t = Table([[P("Details to check before submitting", ParagraphStyle("at", parent=body, fontName="Helvetica-Bold"))]] +
                  [[P(why if why.startswith(lbl) else f"{lbl}: {why}", body)] for lbl, why in attention], colWidths=[W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMBER_BG), ("BOX", (0, 0), (-1, -1), 0.8, AMBER_LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story += [Spacer(1, 10), KeepTogether([t])]

    confirm = (f"Confirmed by the student online on {confirmed_on.strftime('%d %B %Y')}." if confirmed_on
               else "Not yet confirmed by the student.")
    sign = Table([[P("Signature of student", label), P("Date", label)], ["", ""]], colWidths=[W * 0.62, W * 0.38], rowHeights=[None, 12 * mm])
    sign.setStyle(TableStyle([("BOX", (0, 0), (0, -1), 0.4, GRID), ("BOX", (1, 0), (1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, 0), "TOP")]))
    office = Table([[P("For office use only", ParagraphStyle("of", parent=label, fontName="Helvetica-Bold"))],
                    [P("Decision / remarks:", label)], [""]], colWidths=[W], rowHeights=[None, None, 10 * mm])
    office.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), MIST)]))
    story += [KeepTogether([P("Declaration", h), P(DECLARATION, body), Spacer(1, 4), P(confirm, small), Spacer(1, 6), sign, Spacer(1, 8), office])]

    def page(canvas, doc):
        w, ht = A4
        canvas.saveState()
        canvas.setFillColor(NAVY); canvas.rect(0, ht - 28 * mm, w, 28 * mm, stroke=0, fill=1)
        canvas.setFillColor(TEAL); canvas.rect(0, ht - 29.5 * mm, w, 1.5 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold", 20); canvas.drawString(18 * mm, ht - 15 * mm, "Edu Sahaya")
        canvas.setFont("Helvetica", 9); canvas.drawString(18 * mm, ht - 21 * mm, "Simplifying Admissions Through Intelligent Document Processing")
        canvas.setFont("Helvetica-Bold", 12); canvas.drawRightString(w - 18 * mm, ht - 14 * mm, "ADMISSION FORM")
        canvas.setFont("Helvetica", 8.5); canvas.drawRightString(w - 18 * mm, ht - 20 * mm, f"Application No. {application_no}")
        canvas.drawRightString(w - 18 * mm, ht - 25 * mm, status_label)
        if not submitted:
            canvas.saveState(); canvas.setFillColor(colors.HexColor("#163B65")); canvas.setFillAlpha(0.06)
            canvas.setFont("Helvetica-Bold", 90); canvas.translate(w / 2, ht / 2); canvas.rotate(45); canvas.drawCentredString(0, 0, "DRAFT"); canvas.restoreState()
        canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 10 * mm, "Generated from documents submitted by the student. Not an official record or government verification.")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, topMargin=36 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
                      title="Edu Sahaya Admission Form", author="Edu Sahaya").build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def build_admission_form_pdf(db: Session, app: AdmissionApplication) -> bytes:
    """The student's own form. Once submitted it prints the submitted (final) values; before that, the current prefilled form."""
    user = app.user
    submitted = app.status in LOCKED
    form = form_service.build_form(db, user)
    final = final_values(app) if submitted else None
    values = final or {f["key"]: f["value"] for f in form["fields"]}
    subjects = {}
    for d in active_documents(db, user):
        rows = {r.field_name: r.current_value for r in db.scalars(select(ExtractedInformation).where(ExtractedInformation.document_id == d.id))}
        subjects[d.slot] = [(rows.get(f"subject_{i}_name"), rows.get(f"subject_{i}_marks")) for i in range(1, 13) if rows.get(f"subject_{i}_name")]
    return render_admission_form(
        values, subjects, application_no=f"ES-{app.id:06d}",
        status_label=APP_STATUS.get(app.status, app.status) if submitted else "Draft, not yet submitted",
        submitted=submitted, confirmed_on=app.submitted_at if submitted else None,
        attention=[] if submitted else attention_items(form["fields"]))

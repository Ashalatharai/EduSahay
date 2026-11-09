"""Deep Learning and visual layout understanding for uploaded blank admission forms.

Understands the layout of arbitrary college admission forms (PDFs with form fields, flat vector/scanned
PDFs, or images), detects input fields, tables, checkboxes and underlines, and maps them to student data keys.
"""
from dataclasses import dataclass, asdict
import io
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Field key mapping definitions
FIELD_PATTERNS = [
    ("full_name", "personal", [
        r"(?:name\s+of\s+(?:the\s+)?(?:candidate|applicant|student)|candidate['\s]*s?\s*name|applicant['\s]*s?\s*name|student['\s]*s?\s*name|full\s*name|^name(?!\s+of\s+(?:father|mother|school|college|institution|board)))",
    ]),
    ("date_of_birth", "personal", [
        r"(?:date\s+of\s+birth|d\.?o\.?b\.?|birth\s*date)",
    ]),
    ("gender", "personal", [
        r"(?:gender|sex)",
    ]),
    ("gender_male", "personal", [
        r"\b(?:\[\s*\]|\(\s*\)|O|\u25a1)?\s*male\b",
    ]),
    ("gender_female", "personal", [
        r"\b(?:\[\s*\]|\(\s*\)|O|\u25a1)?\s*female\b",
    ]),
    ("aadhaar_number", "personal", [
        r"(?:aadhaar|aadhar|uid)\s*(?:no|number|card(?:\s*no)?)?",
    ]),
    ("father_name", "personal", [
        r"(?:father['\s]*s?\s*name|name\s+of\s+(?:the\s+)?father|guardian['\s]*s?\s*name|name\s+of\s+guardian)",
    ]),
    ("mother_name", "personal", [
        r"(?:mother['\s]*s?\s*name|name\s+of\s+(?:the\s+)?mother)",
    ]),
    ("contact_number", "personal", [
        r"(?:mobile\s*(?:no|number)?|phone\s*(?:no|number)?|contact\s*(?:no|number)?|cell\s*(?:no|number)?|telephone)",
    ]),
    ("email", "personal", [
        r"(?:e-?mail(?:\s*(?:id|address))?)",
    ]),
    ("address", "personal", [
        r"(?:permanent\s+address|residential\s+address|present\s+address|communication\s+address|postal\s+address|^address)",
    ]),
    ("nationality", "personal", [
        r"(?:nationality|citizenship)",
    ]),
    ("category", "personal", [
        r"(?:category|caste|quota)",
    ]),
    ("blood_group", "personal", [
        r"(?:blood\s*group)",
    ]),
    ("sslc_register_number", "academic", [
        r"(?:(?:sslc|10th|matriculation|secondary)\s*(?:reg(?:istration)?\.?\s*(?:no|number)?|roll\s*(?:no|number)?)|reg(?:istration)?\.?\s*(?:no|number)?\s*\(?(?:sslc|10th)\)?)",
    ]),
    ("sslc_school_name", "academic", [
        r"(?:(?:sslc|10th)\s*(?:school|institution)|school\s*(?:name|last\s*attended)|high\s*school)",
    ]),
    ("sslc_exam_year", "academic", [
        r"(?:(?:sslc|10th)\s*(?:year\s*of\s*passing|passing\s*year|exam\s*year)|year\s*of\s*passing\s*\(?(?:sslc|10th)\)?)",
    ]),
    ("sslc_total_marks", "academic", [
        r"(?:(?:sslc|10th)\s*(?:total\s*marks|marks\s*obtained)|marks\s*obtained\s*\(?(?:sslc|10th)\)?)",
    ]),
    ("sslc_percentage", "academic", [
        r"(?:(?:sslc|10th)\s*(?:percentage|%|grade)|percentage\s*\(?(?:sslc|10th)\)?)",
    ]),
    ("puc_register_number", "academic", [
        r"(?:(?:puc|12th|hsc|intermediate|senior\s*secondary)\s*(?:reg(?:istration)?\.?\s*(?:no|number)?|roll\s*(?:no|number)?)|reg(?:istration)?\.?\s*(?:no|number)?\s*\(?(?:puc|12th)\)?)",
    ]),
    ("puc_college_name", "academic", [
        r"(?:(?:puc|12th)\s*(?:college|institution)|college\s*(?:name|last\s*attended)|junior\s*college|pu\s*college)",
    ]),
    ("puc_exam_year", "academic", [
        r"(?:(?:puc|12th)\s*(?:year\s*of\s*passing|passing\s*year|exam\s*year)|year\s*of\s*passing\s*\(?(?:puc|12th)\)?)",
    ]),
    ("puc_total_marks", "academic", [
        r"(?:(?:puc|12th)\s*(?:total\s*marks|marks\s*obtained)|marks\s*obtained\s*\(?(?:puc|12th)\)?)",
    ]),
    ("puc_percentage", "academic", [
        r"(?:(?:puc|12th)\s*(?:percentage|%|grade)|percentage\s*\(?(?:puc|12th)\)?)",
    ]),
]


@dataclass
class FormFieldItem:
    field_id: str
    page: int
    label: str
    label_bbox: list[float]  # [x0, y0, x1, y1]
    input_bbox: list[float]  # [x0, y0, x1, y1]
    field_type: str          # text | checkbox | table_cell | acroform
    matched_key: str | None
    section: str
    confidence: float
    suggested_value: str | None = None
    user_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def match_label_to_key(text: str) -> tuple[str | None, str, float]:
    """Matches text to one of the student field keys. Returns (matched_key, section, confidence)."""
    norm = re.sub(r"[:_.\-]", " ", text).strip().lower()
    for key, section, patterns in FIELD_PATTERNS:
        for pat in patterns:
            if re.search(pat, norm, re.IGNORECASE):
                return key, section, 0.95
    return None, "other", 0.0


def parse_admission_form(file_bytes: bytes, mime_type: str) -> list[FormFieldItem]:
    """Inspects an uploaded PDF or image admission form, detects form fields and their coordinates."""
    if mime_type == "application/pdf" or file_bytes.startswith(b"%PDF"):
        return _parse_pdf_form(file_bytes)
    return _parse_image_form(file_bytes)


def _parse_pdf_form(pdf_bytes: bytes) -> list[FormFieldItem]:
    import fitz

    fields: list[FormFieldItem] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        has_acro = False
        # 1. First check if it has interactive AcroForm widgets
        field_counter = 0
        for page_idx, page in enumerate(doc):
            widgets = list(page.widgets())
            if widgets:
                has_acro = True
                for w in widgets:
                    name = w.field_name or f"field_{field_counter}"
                    rect = [round(w.rect.x0, 1), round(w.rect.y0, 1), round(w.rect.x1, 1), round(w.rect.y1, 1)]
                    ftype = "checkbox" if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX else "acroform"
                    matched_key, section, conf = match_label_to_key(name)
                    fields.append(FormFieldItem(
                        field_id=f"acro_{field_counter}_{name}",
                        page=page_idx,
                        label=name,
                        label_bbox=rect,
                        input_bbox=rect,
                        field_type=ftype,
                        matched_key=matched_key,
                        section=section,
                        confidence=conf if matched_key else 0.5,
                        suggested_value=w.field_value or None,
                    ))
                    field_counter += 1

        if has_acro and fields:
            return fields

        # 2. Flat PDF: extract visual text elements and drawings (lines, underlines, boxes)
        for page_idx, page in enumerate(doc):
            page_fields = _parse_flat_pdf_page(page, page_idx)
            fields.extend(page_fields)

    return fields


def _split_line_into_field_candidates(line_words: list, h_lines: list, page_w: float) -> list[dict]:
    """Finds all distinct label occurrences in a single text line (e.g. 'Aadhaar No: ___ Contact No: ___')."""
    words_info = []
    char_cursor = 0
    full_parts = []
    for w in line_words:
        txt = str(w[4])
        start_char = char_cursor
        end_char = start_char + len(txt)
        words_info.append({"word": txt, "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "start": start_char, "end": end_char})
        full_parts.append(txt)
        char_cursor = end_char + 1
    full_text = " ".join(full_parts)

    matches = []
    for key, section, patterns in FIELD_PATTERNS:
        for pat in patterns:
            for m in re.finditer(pat, full_text, re.IGNORECASE):
                matches.append({"start": m.start(), "end": m.end(), "key": key, "section": section, "label": m.group(0)})

    if not matches:
        return []

    # Sort matches by start position and eliminate overlaps
    matches.sort(key=lambda m: m["start"])
    clean_matches = []
    last_end = -1
    for m in matches:
        if m["start"] >= last_end:
            clean_matches.append(m)
            last_end = m["end"]

    candidates = []
    for i, m in enumerate(clean_matches):
        m_words = [w for w in words_info if not (w["end"] <= m["start"] or w["start"] >= m["end"])]
        if not m_words:
            continue
        l_x0 = min(w["x0"] for w in m_words)
        l_y0 = min(w["y0"] for w in m_words)
        l_x1 = max(w["x1"] for w in m_words)
        l_y1 = max(w["y1"] for w in m_words)

        if i + 1 < len(clean_matches):
            next_start = clean_matches[i + 1]["start"]
            next_words = [w for w in words_info if not (w["end"] <= next_start or w["start"] >= clean_matches[i + 1]["end"])]
            max_right = (min(w["x0"] for w in next_words) - 5) if next_words else (page_w - 40)
        else:
            max_right = page_w - 40

        target_hl = None
        for hl in h_lines:
            if abs(hl["y"] - l_y1) <= 8 and l_x1 - 5 <= hl["x0"] < max_right:
                target_hl = hl
                break

        if target_hl:
            input_bbox = [round(target_hl["x0"] + 2, 1), round(l_y0, 1), round(min(target_hl["x1"], max_right), 1), round(l_y1, 1)]
        else:
            input_bbox = [round(l_x1 + 6, 1), round(l_y0, 1), round(min(l_x1 + 180, max_right), 1), round(l_y1, 1)]

        candidates.append({
            "key": m["key"],
            "section": m["section"],
            "label": m["label"],
            "label_bbox": [round(l_x0, 1), round(l_y0, 1), round(l_x1, 1), round(l_y1, 1)],
            "input_bbox": input_bbox,
        })

    return candidates


def _parse_flat_pdf_page(page, page_idx: int) -> list[FormFieldItem]:
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    rect = page.rect
    page_w, page_h = rect.width, rect.height

    if len(words) < 5:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        return _parse_image_form(img_bytes, page_idx=page_idx, scale_factor=(page_w / pix.width, page_h / pix.height))

    lines_dict: dict[tuple[int, int], list] = {}
    for w in words:
        key = (w[5], w[6])
        lines_dict.setdefault(key, []).append(w)

    sorted_lines = list(lines_dict.values())
    for line_words in sorted_lines:
        line_words.sort(key=lambda x: x[0])
    sorted_lines.sort(key=lambda lw: (min(w[1] for w in lw), min(w[0] for w in lw)))

    raw_lines = []
    for line_words in sorted_lines:
        text = " ".join(x[4] for x in line_words).strip()
        x0 = min(x[0] for x in line_words)
        y0 = min(x[1] for x in line_words)
        x1 = max(x[2] for x in line_words)
        y1 = max(x[3] for x in line_words)
        raw_lines.append({"text": text, "bbox": [x0, y0, x1, y1], "words": line_words})

    drawings = page.get_drawings()
    h_lines = []
    for d in drawings:
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) <= 2.5 and abs(p1.x - p2.x) >= 25:
                    h_lines.append({"x0": min(p1.x, p2.x), "x1": max(p1.x, p2.x), "y": (p1.y + p2.y) / 2})
            elif item[0] == "re":
                r = item[1]
                if r.width >= 25 and r.height <= 30:
                    h_lines.append({"x0": r.x0, "x1": r.x1, "y": r.y1})

    fields: list[FormFieldItem] = []
    seen_keys: set[str] = set()

    for line in raw_lines:
        line_words = line["words"]
        candidates = _split_line_into_field_candidates(line_words, h_lines, page_w)
        for c in candidates:
            k = c["key"]
            if k in seen_keys and k not in ("category", "gender"):
                continue
            fid = f"p{page_idx}_f{len(fields)}_{k}"
            fields.append(FormFieldItem(
                field_id=fid,
                page=page_idx,
                label=c["label"].split(":")[0].strip() or c["label"],
                label_bbox=c["label_bbox"],
                input_bbox=c["input_bbox"],
                field_type="checkbox" if "gender_" in k else "text",
                matched_key=k,
                section=c["section"],
                confidence=0.95,
            ))
            seen_keys.add(k)

    _detect_academic_table_fields(raw_lines, page_idx, fields)
    return fields


def _detect_academic_table_fields(raw_lines: list[dict], page_idx: int, fields: list[FormFieldItem]) -> None:
    """Detects tabular academic grids (SSLC / PUC rows with column headers)."""
    sslc_row = next((l for l in raw_lines if re.search(r"\b(?:sslc|10th)\b", l["text"], re.IGNORECASE) and not any(f.matched_key == "sslc_register_number" for f in fields)), None)
    puc_row = next((l for l in raw_lines if re.search(r"\b(?:puc|12th)\b", l["text"], re.IGNORECASE) and not any(f.matched_key == "puc_register_number" for f in fields)), None)

    if not sslc_row and not puc_row:
        return

    # Look for header line above
    col_headers = [l for l in raw_lines if any(k in l["text"].lower() for k in ("reg", "roll", "school", "college", "year", "marks", "percentage", "%"))]
    if not col_headers:
        return

    # Map column headers to x-positions
    found_cols = []
    for ch in col_headers:
        t = ch["text"].lower()
        if "reg" in t or "roll" in t:
            found_cols.append(("register_number", ch["bbox"][0], ch["bbox"][2]))
        elif "school" in t or "college" in t or "institution" in t:
            found_cols.append(("institution_name", ch["bbox"][0], ch["bbox"][2]))
        elif "year" in t or "passing" in t:
            found_cols.append(("exam_year", ch["bbox"][0], ch["bbox"][2]))
        elif "marks" in t or "total" in t:
            found_cols.append(("total_marks", ch["bbox"][0], ch["bbox"][2]))
        elif "%" in t or "percentage" in t:
            found_cols.append(("percentage", ch["bbox"][0], ch["bbox"][2]))

    for prefix, row in [("sslc", sslc_row), ("puc", puc_row)]:
        if not row:
            continue
        ry0, ry1 = row["bbox"][1], row["bbox"][3]
        for col_name, cx0, cx1 in found_cols:
            full_key = f"{prefix}_{col_name}" if col_name != "institution_name" else (f"sslc_school_name" if prefix == "sslc" else f"puc_college_name")
            if any(f.matched_key == full_key for f in fields):
                continue
            fid = f"p{page_idx}_tbl_{full_key}"
            fields.append(FormFieldItem(
                field_id=fid,
                page=page_idx,
                label=f"{prefix.upper()} {col_name.replace('_', ' ').title()}",
                label_bbox=[round(c, 1) for c in row["bbox"]],
                input_bbox=[round(cx0 + 2, 1), round(ry0, 1), round(cx1 - 2, 1), round(ry1, 1)],
                field_type="table_cell",
                matched_key=full_key,
                section="academic",
                confidence=0.9,
            ))


def _parse_image_form(image_bytes: bytes, page_idx: int = 0, scale_factor: tuple[float, float] = (1.0, 1.0)) -> list[FormFieldItem]:
    """Extracts text elements and field locations from an image using EasyOCR and OpenCV."""
    import cv2
    import numpy as np
    from app.ml.ocr import get_engine

    try:
        engine = get_engine()
    except Exception as e:
        log.warning("OCR engine not available for image form parsing: %s", e)
        return []

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    h, w = img.shape[:2]
    # Run OCR
    ocr_lines = engine.recognise(img)

    fields: list[FormFieldItem] = []
    seen_keys: set[str] = set()

    for idx, line in enumerate(ocr_lines):
        text = line.text.strip()
        xs = [pt[0] for pt in line.box]
        ys = [pt[1] for pt in line.box]
        x0, x1 = min(xs) * scale_factor[0], max(xs) * scale_factor[0]
        y0, y1 = min(ys) * scale_factor[1], max(ys) * scale_factor[1]

        matched_key, section, conf = match_label_to_key(text)
        if not matched_key:
            clean = text.split(":")[0].strip()
            if len(clean) >= 3:
                matched_key, section, conf = match_label_to_key(clean)

        if matched_key and matched_key not in seen_keys:
            fid = f"img_p{page_idx}_f{idx}_{matched_key}"
            right_bound = min(x1 + (220 * scale_factor[0]), w * scale_factor[0] - 20)
            input_bbox = [round(x1 + 6, 1), round(y0, 1), round(right_bound, 1), round(y1, 1)]

            fields.append(FormFieldItem(
                field_id=fid,
                page=page_idx,
                label=text.split(":")[0].strip() or text,
                label_bbox=[round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                input_bbox=input_bbox,
                field_type="checkbox" if "gender_" in matched_key else "text",
                matched_key=matched_key,
                section=section,
                confidence=conf,
            ))
            seen_keys.add(matched_key)

    return fields

"""Turn per-word LayoutLMv3 predictions into fields. Pure Python: no model needed, fully unit-testable."""
from dataclasses import dataclass

from app.ml.extraction_schema import HAS_SUBJECTS, SINGLE_FIELDS


@dataclass
class Span:
    entity: str
    text: str
    confidence: float
    box: list  # [x0, y0, x1, y1]


@dataclass
class FieldResult:
    name: str
    value: str | None
    confidence: float
    box: list | None
    needs_review: bool


def decode_spans(words, boxes, labels, confs) -> list[Span]:
    spans, cur = [], None
    for w, b, l, c in zip(words, boxes, labels, confs):
        if l == "O":
            cur = None
            continue
        prefix, entity = l.split("-", 1)
        if prefix == "B" or cur is None or cur["entity"] != entity:
            cur = {"entity": entity, "words": [], "confs": [], "boxes": []}
            spans.append(cur)
        cur["words"].append(w); cur["confs"].append(c); cur["boxes"].append(b)
    return [Span(s["entity"], " ".join(s["words"]), sum(s["confs"]) / len(s["confs"]),
                 [min(b[0] for b in s["boxes"]), min(b[1] for b in s["boxes"]),
                  max(b[2] for b in s["boxes"]), max(b[3] for b in s["boxes"])]) for s in spans]


def _cy(s): return (s.box[1] + s.box[3]) / 2


def build_fields(doc_type: str, spans: list[Span], min_conf: float = 0.7) -> list[FieldResult]:
    out = []
    for entity, name in SINGLE_FIELDS[doc_type].items():
        cands = [s for s in spans if s.entity == entity]
        best = max(cands, key=lambda s: s.confidence, default=None)
        out.append(FieldResult(name, best.text if best else None, best.confidence if best else 0.0,
                               best.box if best else None, best is None or best.confidence < min_conf))
    if doc_type in HAS_SUBJECTS:
        marks = [s for s in spans if s.entity == "MARKS"]
        used = set()
        for i, subj in enumerate(sorted((s for s in spans if s.entity == "SUBJECT"), key=_cy), 1):
            height = subj.box[3] - subj.box[1]
            options = [(abs(_cy(m) - _cy(subj)), j) for j, m in enumerate(marks)
                       if j not in used and m.box[0] > subj.box[0] and abs(_cy(m) - _cy(subj)) <= 1.5 * height]
            out.append(FieldResult(f"subject_{i}_name", subj.text, subj.confidence, subj.box, subj.confidence < min_conf))
            if options:
                j = min(options)[1]; used.add(j); m = marks[j]
                out.append(FieldResult(f"subject_{i}_marks", m.text, m.confidence, m.box, m.confidence < min_conf))
            else:
                out.append(FieldResult(f"subject_{i}_marks", None, 0.0, None, True))
    return out


def words_from_lines(lines: list[dict]) -> tuple[list[str], list[list[int]]]:
    """OCR gives text lines; LayoutLMv3 wants words. Split each line, sharing its box by character count."""
    words, boxes = [], []
    for l in lines:
        xs = [p[0] for p in l["box"]]; ys = [p[1] for p in l["box"]]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        parts = l["text"].split()
        total = sum(len(p) + 1 for p in parts) or 1
        cx = x0
        for p in parts:
            w = (x1 - x0) * (len(p) + 1) / total
            words.append(p); boxes.append([int(cx), int(y0), int(cx + w - (x1 - x0) / total), int(y1)])
            cx += w
    return words, boxes


def extract_fields_from_ocr(doc_type: str, lines: list[dict]) -> list[FieldResult]:
    """Pattern and heuristic information extraction fallback when LayoutLMv3 weights are not present."""
    import re
    from app.services.validation import parse_date

    texts = [l["text"].strip() for l in lines if l.get("text", "").strip()]
    full_text = "\n".join(texts)
    extracted = {}

    if doc_type == "aadhaar":
        m_aadh = re.search(r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b|XXXX\s+XXXX\s+(\d{4})", full_text)
        if m_aadh:
            extracted["aadhaar_number_masked"] = (m_aadh.group(0), 0.95)

        m_gen = re.search(r"\b(Male|Female|Transgender)\b", full_text, re.IGNORECASE)
        if m_gen:
            extracted["gender"] = (m_gen.group(1).capitalize(), 0.95)

        m_dob = re.search(r"(?:DOB|Date\s*of\s*Birth|Year\s*of\s*Birth)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4})", full_text, re.IGNORECASE)
        if m_dob:
            d_str = m_dob.group(1)
            d = parse_date(d_str)
            if d:
                extracted["date_of_birth"] = (f"{d.day:02d}/{d.month:02d}/{d.year}", 0.95)
            elif len(d_str) == 4 and d_str.isdigit():
                extracted["date_of_birth"] = (f"01/01/{d_str}", 0.8)

        ignore_words = {"GOVERNMENT", "INDIA", "ENROLMENT", "UNIQUE", "IDENTIFICATION", "AUTHORITY", "MALE", "FEMALE", "DOB", "YEAR", "HELP"}
        for i, t in enumerate(texts):
            clean = re.sub(r"[^A-Za-z\s]", "", t).strip()
            tokens = [tok for tok in clean.split() if tok.upper() not in ignore_words]
            if 2 <= len(tokens) <= 4 and all(len(tok) > 1 for tok in tokens):
                nearby = " ".join(texts[max(0, i-1):min(len(texts), i+3)])
                if re.search(r"(?:DOB|Birth|Male|Female)", nearby, re.IGNORECASE):
                    extracted["student_name"] = (" ".join(tokens).upper(), 0.9)
                    break

    elif doc_type in ("sslc", "puc"):
        m_reg = re.search(r"(?:Reg(?:ister)?\.?\s*(?:No|Number)?|Roll\s*(?:No)?)\s*[:\-]?\s*([A-Za-z0-9\-]{5,15})", full_text, re.IGNORECASE)
        if m_reg:
            extracted["register_number"] = (m_reg.group(1).upper(), 0.92)

        m_yr = re.search(r"(?:Year|Exam(?:ination)?\s*Year|Month\s*&\s*Year|Passing\s*Year)\s*[:\-]?\s*(?:[A-Za-z]+\s*)?((?:19|20)\d{2})", full_text, re.IGNORECASE)
        if m_yr:
            extracted["exam_year"] = (m_yr.group(1), 0.9)
        else:
            m_yr_gen = re.findall(r"\b(19\d{2}|20\d{2})\b", full_text)
            if m_yr_gen:
                extracted["exam_year"] = (m_yr_gen[-1], 0.8)

        m_pct = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*%", full_text)
        if m_pct:
            extracted["percentage"] = (m_pct.group(1), 0.92)

        m_tot = re.search(r"(?:Total\s*Marks|Grand\s*Total|Marks\s*Obtained)\s*[:\-]?\s*(\d{2,4})", full_text, re.IGNORECASE)
        if m_tot:
            extracted["total_marks"] = (m_tot.group(1), 0.9)

        if doc_type == "sslc":
            m_sch = re.search(r"([A-Za-z0-9\s,\.\-']+(?:HIGH\s+SCHOOL|SCHOOL|VIDYALAYA|ACADEMY)[A-Za-z0-9\s,\.\-']*)", full_text, re.IGNORECASE)
            if m_sch:
                extracted["school_name"] = (m_sch.group(1).strip()[:100], 0.88)
        else:
            m_col = re.search(r"([A-Za-z0-9\s,\.\-']+(?:PU\s+COLLEGE|COLLEGE|JUNIOR\s+COLLEGE|INSTITUTE)[A-Za-z0-9\s,\.\-']*)", full_text, re.IGNORECASE)
            if m_col:
                extracted["college_name"] = (m_col.group(1).strip()[:100], 0.88)

        m_name = re.search(r"(?:Name\s*of\s*(?:the\s*)?(?:Candidate|Student)|Candidate['\s]*s?\s*Name|Student['\s]*s?\s*Name)\s*[:\-]?\s*([A-Za-z\s\.]{3,50})", full_text, re.IGNORECASE)
        if m_name:
            cname = m_name.group(1).strip()
            if len(cname) > 3:
                extracted["student_name"] = (cname.upper(), 0.92)

        if "student_name" not in extracted:
            for t in texts[:10]:
                if any(k in t.upper() for k in ("BOARD", "KARNATAKA", "MARKS", "STATEMENT", "CERTIFICATE", "SECONDARY")):
                    continue
                clean = re.sub(r"[^A-Za-z\s]", "", t).strip()
                tokens = clean.split()
                if 2 <= len(tokens) <= 4 and all(len(tok) > 1 for tok in tokens) and clean.isupper():
                    extracted["student_name"] = (clean, 0.82)
                    break

        if "date_of_birth" not in extracted and doc_type == "sslc":
            m_dob = re.search(r"(?:DOB|Date\s*of\s*Birth)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})", full_text, re.IGNORECASE)
            if m_dob:
                d = parse_date(m_dob.group(1))
                if d:
                    extracted["date_of_birth"] = (f"{d.day:02d}/{d.month:02d}/{d.year}", 0.9)

    out = []
    single_fields = SINGLE_FIELDS.get(doc_type, {})
    for entity, name in single_fields.items():
        val_conf = extracted.get(name)
        if val_conf:
            val, conf = val_conf
            out.append(FieldResult(name=name, value=val, confidence=conf, box=None, needs_review=(conf < 0.7)))
        else:
            out.append(FieldResult(name=name, value=None, confidence=0.0, box=None, needs_review=True))
    return out

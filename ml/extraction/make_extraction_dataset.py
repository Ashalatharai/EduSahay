"""Annotated FICTIONAL documents for fine-tuning LayoutLMv3 (words + boxes + BIO labels + ground-truth fields).

Layouts are invented, so a model fine-tuned on this data demonstrates the pipeline only; it is a prototype and says
nothing about accuracy on real documents. Replace with authorized, consented, annotated scans for real use.
"""
import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "classifier"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from make_synthetic_dataset import SSLC_SUBJ, PUC_SUBJ, FIRST, LAST, digits, font, person  # noqa: E402


class Page:
    def __init__(self, W, H, bg=(255, 255, 255)):
        self.img = Image.new("RGB", (W, H), bg)
        self.d = ImageDraw.Draw(self.img)
        self.words, self.fields = [], {}

    def text(self, xy, s, size, bold=False, fill=(25, 25, 25), anchor="la", entity=None):
        f = font(size, bold)
        self.d.text(xy, s, font=f, fill=fill, anchor=anchor)
        x0, y0, _, y1 = self.d.textbbox(xy, s, font=f, anchor=anchor)
        pos, first = 0, True
        for w in s.split():
            start = s.index(w, pos)
            self.words.append({"text": w, "box": [x0 + f.getlength(s[:start]), y0, x0 + f.getlength(s[:start + len(w)]), y1],
                               "entity": entity, "first": first})
            first, pos = False, start + len(w)

    def pair(self, x, y, key, value, size, entity, bold=False):
        """Label text (not a field) followed by a value (a field)."""
        self.text((x, y), key, size, bold)
        self.text((x + font(size, bold).getlength(key + " "), y), value, size, entity=entity)

    def table(self, x, y, widths, row_h, rows, size, entity_of):
        for i, row in enumerate(rows):
            cx = x
            for j, (w, cell) in enumerate(zip(widths, row)):
                self.d.rectangle([cx, y, cx + w, y + row_h], outline=(40, 40, 40))
                if str(cell):
                    self.text((cx + 6, y + row_h / 2), str(cell), size, bold=(i == 0), anchor="lm", entity=entity_of(i, j, len(rows)))
                cx += w
            y += row_h
        return y


def date(r, lo, hi):
    return f"{r.randint(1, 28):02d}/{r.randint(1, 12):02d}/{r.randint(lo, hi)}"


def aadhaar_doc(r):
    W = r.randint(560, 900); H = int(W * r.uniform(0.60, 0.66)); p = Page(W, H, r.choice([(255, 255, 255), (252, 250, 245)]))
    p.d.rectangle([0, 0, W, H * 0.16], fill=r.choice([(230, 120, 30), (30, 60, 140), (40, 130, 70)]))
    p.text((W / 2, H * 0.08), "IDENTITY CARD (SPECIMEN)", H * 0.07, True, (255, 255, 255), "mm")
    p.d.rectangle([W * 0.05, H * 0.28, W * 0.27, H * 0.73], fill=(190, 190, 195))
    name, dob, gender, num = person(r), date(r, 1998, 2009), r.choice(["Male", "Female"]), f"XXXX XXXX {digits(r, 4)}"
    s = H * 0.065
    p.text((W * 0.33, H * 0.30), name, s, True, entity="NAME")
    p.pair(W * 0.33, H * 0.43, "DOB:", dob, s, "DOB")
    p.text((W * 0.33, H * 0.56), gender, s, entity="GENDER")
    p.text((W / 2, H * 0.86), num, H * 0.10, True, anchor="mm", entity="AADHAAR_NO")
    p.fields.update(student_name=name, date_of_birth=dob, gender=gender, aadhaar_number_masked=num)
    return p


def sslc_doc(r):
    W = r.randint(600, 800); H = int(W * 1.41); p = Page(W, H)
    p.d.rectangle([12, 12, W - 12, H - 12], outline=(30, 30, 30), width=3)
    p.text((W / 2, H * 0.13), "SECONDARY SCHOOL LEAVING CERTIFICATE", W * 0.034, True, anchor="mm")
    p.text((W / 2, H * 0.16), "STATEMENT OF MARKS (SPECIMEN)", W * 0.03, anchor="mm")
    reg, name, dob = digits(r, 7), person(r), date(r, 2004, 2009)
    school, year = f"{r.choice(LAST)} High School", str(r.randint(2018, 2024)); s = W * 0.028
    for i, (k, v, e) in enumerate([("REGISTER NO", reg, "REG_NO"), ("NAME", name, "NAME"), ("DATE OF BIRTH", dob, "DOB"),
                                   ("SCHOOL", school, "SCHOOL"), ("YEAR", year, "YEAR")]):
        y = H * (0.21 + 0.03 * i)
        p.text((W * 0.08, y), k, s, True); p.text((W * 0.38, y), v, s, entity=e)
    rows, marks = [["Subject", "Max", "Min", "Marks"]], []
    for i, sub in enumerate(SSLC_SUBJ):
        mx = 125 if i < 3 else 100; m = r.randint(40, mx - 5); marks.append(m)
        rows.append([sub, mx, 35 if i < 3 else 28, m]); p.fields[f"subject_{i + 1}_name"] = sub; p.fields[f"subject_{i + 1}_marks"] = str(m)
    total = sum(marks); rows.append(["TOTAL", 625, "", total])
    ent = lambda i, j, n: ("SUBJECT" if j == 0 else "MARKS" if j == 3 else None) if 0 < i < n - 1 else ("TOTAL" if (i == n - 1 and j == 3) else None)
    y = p.table(W * 0.08, H * 0.38, [W * 0.44, W * 0.14, W * 0.14, W * 0.16], H * 0.04, rows, W * 0.026, ent)
    pct = f"{total / 625 * 100:.2f}%"
    p.pair(W * 0.08, y + H * 0.03, "PERCENTAGE:", pct, W * 0.03, "PERCENT", bold=True)
    p.fields.update(student_name=name, register_number=reg, date_of_birth=dob, school_name=school, exam_year=year,
                    total_marks=str(total), percentage=pct)
    return p


def puc_doc(r):
    W = r.randint(600, 800); H = int(W * 1.41); p = Page(W, H)
    p.d.rectangle([0, 0, W, H * 0.12], fill=(25, 45, 90))
    p.text((W / 2, H * 0.045), "PRE-UNIVERSITY COURSE", W * 0.04, True, (255, 255, 255), "mm")
    p.text((W / 2, H * 0.085), f"MARKS STATEMENT - {r.choice(['SCIENCE', 'COMMERCE', 'ARTS'])} (SPECIMEN)", W * 0.027, False, (255, 255, 255), "mm")
    reg, name, college, year = digits(r, 8), person(r), f"{r.choice(LAST)} PU College", str(r.randint(2020, 2025)); s = W * 0.026
    p.pair(W * 0.06, H * 0.15, "REG NO:", reg, s, "REG_NO"); p.pair(W * 0.06, H * 0.18, "NAME:", name, s, "NAME", True)
    p.pair(W * 0.50, H * 0.15, "COLLEGE:", college, s, "COLLEGE"); p.pair(W * 0.50, H * 0.18, "YEAR:", year, s, "YEAR")
    rows = [["Subject", "T.Max", "T.Obt", "P.Max", "P.Obt", "Total", "Result"]]
    for i, sub in enumerate(r.sample(PUC_SUBJ, 6)):
        t, pr = r.randint(40, 68), r.randint(15, 29)
        rows.append([sub, 70, t, 30, pr, t + pr, "P"]); p.fields[f"subject_{i + 1}_name"] = sub; p.fields[f"subject_{i + 1}_marks"] = str(t + pr)
    total = sum(int(x[5]) for x in rows[1:]); rows.append(["GRAND TOTAL", "", "", "", "", total, "PASS"])
    ent = lambda i, j, n: ("SUBJECT" if j == 0 else "MARKS" if j == 5 else None) if 0 < i < n - 1 else ("TOTAL" if (i == n - 1 and j == 5) else None)
    y = p.table(W * 0.05, H * 0.24, [W * 0.30, W * 0.10, W * 0.10, W * 0.10, W * 0.10, W * 0.11, W * 0.14], H * 0.038, rows, W * 0.022, ent)
    pct = f"{total / 600 * 100:.1f} %"
    p.text((W * 0.06, y + H * 0.05), pct, W * 0.035, True, entity="PERCENT")
    p.fields.update(student_name=name, register_number=reg, college_name=college, exam_year=year, total_marks=str(total), percentage=pct)
    return p


def finish(p, r):
    """Scanner-style degradation; word boxes are transformed with the image so annotations stay aligned."""
    W, H = p.img.size; bg = r.randint(190, 255); m = r.uniform(0.03, 0.10); ox, oy = int(W * m), int(H * m)
    canvas = Image.new("L", (int(W * (1 + 2 * m)), int(H * (1 + 2 * m))), bg); canvas.paste(p.img.convert("L"), (ox, oy))
    a = np.array(canvas); h, w = a.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), r.uniform(-1.5, 1.5), 1)  # small: production images are already deskewed before OCR
    a = cv2.warpAffine(a, M, (w, h), borderValue=int(bg))
    words, labels = [], []
    for wd in p.words:
        x0, y0, x1, y1 = wd["box"]
        pts = np.array([[x0 + ox, y0 + oy, 1], [x1 + ox, y0 + oy, 1], [x1 + ox, y1 + oy, 1], [x0 + ox, y1 + oy, 1]], float)
        t = (M @ pts.T).T
        box = [int(max(0, t[:, 0].min())), int(max(0, t[:, 1].min())), int(min(w - 1, t[:, 0].max())), int(min(h - 1, t[:, 1].max()))]
        words.append({"text": wd["text"], "box": box})
        labels.append("O" if wd["entity"] is None else ("B-" if wd["first"] else "I-") + wd["entity"])
    if r.random() < 0.5: a = cv2.GaussianBlur(a, (0, 0), r.uniform(0.3, 1.0))
    a = np.clip(a.astype(np.float32) * r.uniform(0.8, 1.1) + r.uniform(-20, 10) + np.random.RandomState(r.randint(0, 9999)).randn(h, w) * r.uniform(0, 6), 0, 255).astype(np.uint8)
    a = cv2.imdecode(cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, r.randint(50, 95)])[1], cv2.IMREAD_GRAYSCALE)
    return a, words, labels


MAKERS = {"aadhaar": aadhaar_doc, "sslc": sslc_doc, "puc": puc_doc}


def generate(out, counts, seed=0):
    out = Path(out)
    for split, n in counts.items():
        (out / split / "images").mkdir(parents=True, exist_ok=True)
        with open(out / split / "annotations.jsonl", "w") as f:
            for doc_type, make in MAKERS.items():
                for i in range(n):
                    r = random.Random(f"{seed}-{split}-{doc_type}-{i}")
                    page = make(r)
                    img, words, labels = finish(page, r)
                    name = f"{doc_type}_{i:04d}.png"
                    cv2.imwrite(str(out / split / "images" / name), img)
                    f.write(json.dumps({"image": f"images/{name}", "doc_type": doc_type, "width": img.shape[1], "height": img.shape[0],
                                        "words": [w["text"] for w in words], "boxes": [w["box"] for w in words],
                                        "labels": labels, "fields": page.fields}) + "\n")
    (out / "meta.json").write_text(json.dumps({"type": "synthetic", "seed": seed, "per_doc_type": counts,
                                               "note": "Fictional documents; results do not reflect real-document accuracy."}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../datasets/extraction")
    ap.add_argument("--train", type=int, default=150); ap.add_argument("--val", type=int, default=30); ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    generate(a.out, {"train": a.train, "val": a.val, "test": a.test}, a.seed)
    print(f"Dataset written to {a.out}")

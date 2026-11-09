"""Generate a FICTIONAL labelled document dataset (no real student data).

Layouts are invented, loosely inspired by the document types: they are NOT real Aadhaar/SSLC/PUC scans.
A model trained on this data shows the pipeline works; it will not be accurate on real documents.
Replace or extend with authorized, consented scans for real performance.
"""
import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

LABELS = ["aadhaar", "sslc", "puc", "other"]
FIRST = ["Ananya", "Rohan", "Meera", "Karthik", "Divya", "Arjun", "Sneha", "Varun", "Pooja", "Nikhil", "Lakshmi", "Suresh"]
LAST = ["Rao", "Shetty", "Naik", "Gowda", "Bhat", "Kamath", "Hegde", "Poojary", "Kumar", "Prabhu"]
SSLC_SUBJ = ["First Language", "Second Language", "Third Language", "Mathematics", "Science", "Social Science"]
PUC_SUBJ = ["Kannada", "English", "Physics", "Chemistry", "Mathematics", "Computer Science", "Biology", "Electronics"]
WORDS = "report term account office notice please review attached regarding payment service sample record district annual meeting update".split()
_fonts = {}


def font(size, bold=False):
    key = (int(size), bold)
    if key not in _fonts:
        try:
            _fonts[key] = ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", int(size))
        except OSError:
            _fonts[key] = ImageFont.load_default(int(size))
    return _fonts[key]


def person(r):
    return f"{r.choice(FIRST)} {r.choice(LAST)}".upper()


def digits(r, n):
    return "".join(str(r.randint(0, 9)) for _ in range(n))


def txt(d, xy, s, size, bold=False, fill=(25, 25, 25), anchor="la"):
    d.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)


def table(d, x, y, widths, row_h, rows, size):
    for i, row in enumerate(rows):
        cx = x
        for w, cell in zip(widths, row):
            d.rectangle([cx, y, cx + w, y + row_h], outline=(40, 40, 40), width=1)
            txt(d, (cx + 6, y + row_h / 2), str(cell), size, bold=(i == 0), anchor="lm")
            cx += w
        y += row_h
    return y


def lines(d, x, y, w, n, r, size, gap):
    for _ in range(n):
        txt(d, (x, y), " ".join(r.choice(WORDS) for _ in range(r.randint(5, max(6, int(w / (size * 4.2)))))), size, fill=(60, 60, 60))
        y += gap
    return y


def aadhaar(r):
    W = r.randint(560, 900); H = int(W * r.uniform(0.60, 0.66))
    img = Image.new("RGB", (W, H), r.choice([(255, 255, 255), (252, 250, 245), (248, 252, 255)]))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H * 0.16], fill=r.choice([(230, 120, 30), (30, 60, 140), (40, 130, 70)]))
    txt(d, (W / 2, H * 0.08), "IDENTITY CARD (SPECIMEN)", H * 0.07, True, (255, 255, 255), "mm")
    d.rectangle([W * 0.05, H * 0.28, W * 0.27, H * 0.73], fill=(190, 190, 195))
    d.ellipse([W * 0.10, H * 0.34, W * 0.22, H * 0.50], fill=(120, 120, 125))
    for i, s in enumerate([person(r), f"DOB: {r.randint(1,28):02d}/{r.randint(1,12):02d}/{r.randint(1998,2009)}", r.choice(["Male", "Female"])]):
        txt(d, (W * 0.33, H * (0.30 + 0.13 * i)), s, H * 0.065, bold=(i == 0))
    qx, qy, q = W * 0.72, H * 0.28, H * 0.34
    for i in range(10):
        for j in range(10):
            if r.random() < 0.5:
                d.rectangle([qx + i * q / 10, qy + j * q / 10, qx + (i + 1) * q / 10, qy + (j + 1) * q / 10], fill=(0, 0, 0))
    txt(d, (W / 2, H * 0.86), f"XXXX XXXX {digits(r, 4)}", H * 0.10, True, anchor="mm")
    return img


def sslc(r):
    W = r.randint(600, 800); H = int(W * 1.41)
    img = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.rectangle([12, 12, W - 12, H - 12], outline=(30, 30, 30), width=3)
    d.ellipse([W / 2 - W * 0.05, H * 0.03, W / 2 + W * 0.05, H * 0.03 + W * 0.1], outline=(30, 30, 30), width=3)
    txt(d, (W / 2, H * 0.13), "SECONDARY SCHOOL LEAVING CERTIFICATE", W * 0.034, True, anchor="mm")
    txt(d, (W / 2, H * 0.16), "STATEMENT OF MARKS (SPECIMEN)", W * 0.03, anchor="mm")
    info = [("REGISTER NO", digits(r, 7)), ("NAME", person(r)), ("DATE OF BIRTH", f"{r.randint(1,28):02d}/{r.randint(1,12):02d}/{r.randint(2004,2009)}"),
            ("SCHOOL", f"{r.choice(LAST)} High School"), ("YEAR", str(r.randint(2018, 2024)))]
    y = H * 0.21
    for k, v in info:
        txt(d, (W * 0.08, y), k, W * 0.028, True); txt(d, (W * 0.38, y), v, W * 0.028); y += H * 0.03
    rows = [["Subject", "Max", "Min", "Marks"]] + [[s, 125 if i < 3 else 100, 35 if i < 3 else 28, r.randint(40, 120 if i < 3 else 98)] for i, s in enumerate(SSLC_SUBJ)]
    rows.append(["TOTAL", 625, "", sum(x[3] for x in rows[1:])])
    y = table(d, W * 0.08, H * 0.38, [W * 0.44, W * 0.14, W * 0.14, W * 0.16], H * 0.04, rows, W * 0.026)
    txt(d, (W * 0.08, y + H * 0.03), f"PERCENTAGE: {r.uniform(55, 98):.2f}%", W * 0.03, True)
    d.line([W * 0.1, H * 0.9, W * 0.3, H * 0.9], fill=(30, 30, 30), width=2); d.line([W * 0.7, H * 0.9, W * 0.9, H * 0.9], fill=(30, 30, 30), width=2)
    return img


def puc(r):
    W = r.randint(600, 800); H = int(W * 1.41)
    img = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H * 0.12], fill=(25, 45, 90))
    txt(d, (W / 2, H * 0.045), "PRE-UNIVERSITY COURSE", W * 0.04, True, (255, 255, 255), "mm")
    txt(d, (W / 2, H * 0.085), f"MARKS STATEMENT - {r.choice(['SCIENCE', 'COMMERCE', 'ARTS'])} (SPECIMEN)", W * 0.027, False, (255, 255, 255), "mm")
    left = [("REG NO", digits(r, 8)), ("NAME", person(r))]; right = [("COLLEGE", f"{r.choice(LAST)} PU College"), ("YEAR", str(r.randint(2020, 2025)))]
    for i, (k, v) in enumerate(left):
        txt(d, (W * 0.06, H * (0.15 + 0.03 * i)), f"{k}: {v}", W * 0.026, i == 1)
    for i, (k, v) in enumerate(right):
        txt(d, (W * 0.55, H * (0.15 + 0.03 * i)), f"{k}: {v}", W * 0.026)
    subs = r.sample(PUC_SUBJ, 6)
    rows = [["Subject", "T.Max", "T.Obt", "P.Max", "P.Obt", "Total", "Result"]]
    for s in subs:
        t, p = r.randint(40, 70), r.randint(15, 30)
        rows.append([s, 70, t, 30, p, t + p, "P"])
    rows.append(["GRAND TOTAL", "", "", "", "", sum(x[5] for x in rows[1:]), "PASS"])
    y = table(d, W * 0.05, H * 0.24, [W * 0.30, W * 0.10, W * 0.10, W * 0.10, W * 0.10, W * 0.11, W * 0.14], H * 0.038, rows, W * 0.022)
    d.rectangle([W * 0.05, y + H * 0.03, W * 0.4, y + H * 0.08], outline=(25, 45, 90), width=3)
    txt(d, (W * 0.225, y + H * 0.055), f"{r.uniform(55, 98):.1f} %", W * 0.035, True, anchor="mm")
    txt(d, (W * 0.95, H * 0.93), "Controller of Examinations", W * 0.024, anchor="rm")
    return img


def other(r):
    kind = r.choice(["letter", "invoice", "statement", "form", "receipt", "photo", "blank"])
    W = r.randint(300, 380) if kind == "receipt" else r.randint(600, 800)
    H = r.randint(700, 900) if kind == "receipt" else int(W * r.choice([1.41, 1.29, 0.75]))
    img = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    s = W * 0.03
    if kind == "letter":
        txt(d, (W * 0.08, H * 0.06), f"{r.randint(1,28)} Nov 2025", s); y = lines(d, W * 0.08, H * 0.12, W, 3, r, s, s * 1.5)
        txt(d, (W * 0.08, y + s), "Subject: " + " ".join(r.sample(WORDS, 3)), s * 1.1, True)
        y += s * 3
        for _ in range(4):
            y = lines(d, W * 0.08, y, W, r.randint(4, 7), r, s, s * 1.4) + s
    elif kind in ("invoice", "statement"):
        txt(d, (W * 0.08, H * 0.06), kind.upper(), W * 0.05, True)
        n = r.randint(5, 9) if kind == "invoice" else r.randint(16, 22)
        rows = [["Item", "Qty", "Rate", "Amount"] if kind == "invoice" else ["Date", "Ref", "Debit", "Credit", "Balance"]]
        rows += [[r.choice(WORDS).title()] + [r.randint(1, 999) for _ in range(len(rows[0]) - 1)] for _ in range(n)]
        w = W * 0.84 / len(rows[0]); table(d, W * 0.08, H * 0.15, [w] * len(rows[0]), H * (0.05 if kind == "invoice" else 0.032), rows, s * 0.9)
    elif kind == "form":
        txt(d, (W / 2, H * 0.07), "APPLICATION FORM", W * 0.045, True, anchor="mm")
        for i in range(r.randint(7, 11)):
            y = H * (0.15 + 0.07 * i); txt(d, (W * 0.08, y), r.choice(WORDS).title() + ":", s); d.line([W * 0.35, y + s * 1.2, W * 0.92, y + s * 1.2], fill=(40, 40, 40))
            if r.random() < 0.3: d.rectangle([W * 0.94, y, W * 0.94 + s, y + s], outline=(40, 40, 40))
    elif kind == "receipt":
        y = H * 0.05
        while y < H * 0.9:
            txt(d, (W / 2, y), r.choice(WORDS).upper() + " " + str(r.randint(10, 999)), s * 1.1, anchor="mm"); y += s * 2
    elif kind == "photo":
        g = np.linspace(r.randint(40, 200), r.randint(40, 200), W)[None, :].repeat(H, 0)
        img = Image.fromarray(np.clip(g + np.random.RandomState(r.randint(0, 9999)).randn(H, W) * 12, 0, 255).astype(np.uint8)).convert("RGB"); d = ImageDraw.Draw(img)
        for _ in range(r.randint(2, 5)):
            x, y = r.randint(0, W), r.randint(0, H); rad = r.randint(30, 160); c = r.randint(20, 230)
            d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(c, c, c))
    else:
        for _ in range(r.randint(0, 3)):
            lines(d, W * 0.1, H * r.uniform(0.1, 0.9), W, 1, r, s, s)
    return img


def scan(img, r):
    """Place on a scanner-like background and add rotation, blur, lighting, noise and JPEG artefacts."""
    bg = r.randint(190, 255); m = r.uniform(0.03, 0.10)
    W, H = img.size; canvas = Image.new("L", (int(W * (1 + 2 * m)), int(H * (1 + 2 * m))), bg)
    canvas.paste(img.convert("L"), (int(W * m), int(H * m)))
    a = np.array(canvas)
    h, w = a.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), r.uniform(-4, 4), 1)
    a = cv2.warpAffine(a, M, (w, h), borderValue=int(bg))
    if r.random() < 0.6: a = cv2.GaussianBlur(a, (0, 0), r.uniform(0.3, 1.3))
    a = np.clip(a.astype(np.float32) * r.uniform(0.75, 1.1) + r.uniform(-25, 15) + np.random.RandomState(r.randint(0, 9999)).randn(h, w) * r.uniform(0, 8), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, r.randint(35, 95)])
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def generate(out, counts, seed=0):
    out = Path(out)
    makers = dict(zip(LABELS, [aadhaar, sslc, puc, other]))
    for split, n in counts.items():
        for label, fn in makers.items():
            d = out / split / label; d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                r = random.Random(f"{seed}-{split}-{label}-{i}")
                cv2.imwrite(str(d / f"{i:04d}.png"), scan(fn(r), r))
    (out / "meta.json").write_text(json.dumps({
        "type": "synthetic", "seed": seed, "per_class": counts,
        "note": "Fictional documents with invented layouts. Results do not reflect real-document accuracy."}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../datasets/classifier")
    ap.add_argument("--train", type=int, default=200); ap.add_argument("--val", type=int, default=40); ap.add_argument("--test", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    generate(a.out, {"train": a.train, "val": a.val, "test": a.test}, a.seed)
    print(f"Dataset written to {a.out}")

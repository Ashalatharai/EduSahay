"""Deep Learning OCR (PaddleOCR: text detection + recognition) behind a small engine interface."""
from dataclasses import dataclass
from functools import lru_cache
from statistics import median

import numpy as np

from app.core.config import settings
from app.ml.errors import ModelNotAvailable
from app.ml.ocr_preprocess import apply_rotation, prepare_for_ocr


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: list  # four [x, y] corner points, in pixels of the preprocessed image


class PaddleOcrEngine:
    name = "paddleocr"

    def __init__(self):
        import paddleocr
        from paddleocr import PaddleOCR

        self.version = getattr(paddleocr, "__version__", "unknown")
        self._ocr = PaddleOCR(
            use_doc_orientation_classify=False,  # page rotation is handled in run_ocr
            use_doc_unwarping=False,
            use_textline_orientation=True,  # fixes upside-down lines
            lang=settings.ocr_lang,
        )

    def recognise(self, image: np.ndarray) -> list[OcrLine]:
        lines = []
        for res in self._ocr.predict(image):
            for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
                if str(text).strip():
                    lines.append(OcrLine(str(text), float(score), np.asarray(poly).astype(int).tolist()))
        return lines


class EasyOcrEngine:
    name = "easyocr"

    def __init__(self):
        import easyocr
        from pathlib import Path
        model_dir = str(Path(__file__).resolve().parents[3] / "ml" / "easyocr_models")
        Path(model_dir).mkdir(parents=True, exist_ok=True)
        self.version = getattr(easyocr, "__version__", "1.7.2")
        self._reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=model_dir,
                                      user_network_directory=model_dir, download_enabled=False)

    def recognise(self, image: np.ndarray) -> list[OcrLine]:
        results = self._reader.readtext(image)
        lines = []
        for bbox, text, score in results:
            if str(text).strip():
                poly = [[int(pt[0]), int(pt[1])] for pt in bbox]
                lines.append(OcrLine(str(text).strip(), float(score), poly))
        return lines


@lru_cache(maxsize=1)
def get_engine():
    try:
        import paddleocr  # noqa: F401
        return PaddleOcrEngine()
    except Exception:
        pass
    try:
        import easyocr  # noqa: F401
        return EasyOcrEngine()
    except ImportError as e:
        raise ModelNotAvailable("PaddleOCR or EasyOCR is not installed") from e
    except Exception as e:
        raise ModelNotAvailable(f"OCR engine could not start ({type(e).__name__})") from e


def reading_order(lines: list[OcrLine]) -> list[OcrLine]:
    """Top-to-bottom, left-to-right: lines whose centres are close vertically form one row."""
    if not lines:
        return []
    cy = lambda l: sum(p[1] for p in l.box) / 4
    cx = lambda l: sum(p[0] for p in l.box) / 4
    tol = 0.6 * median(max(p[1] for p in l.box) - min(p[1] for p in l.box) for l in lines)
    rows: list[list[OcrLine]] = []
    for l in sorted(lines, key=cy):
        if rows and abs(cy(l) - sum(map(cy, rows[-1])) / len(rows[-1])) <= tol:
            rows[-1].append(l)
        else:
            rows.append([l])
    return [l for row in rows for l in sorted(row, key=cx)]


def _quality(lines: list[OcrLine]) -> float:
    return sum(l.confidence * len(l.text) for l in lines)


def _good_enough(lines: list[OcrLine]) -> bool:
    return len(lines) >= 3 and sum(l.confidence for l in lines) / len(lines) >= 0.6


def run_ocr(content: bytes, engine=None) -> dict:
    """Preprocess, read text, and if the first pass looks poor retry the page rotated by 90/180/270 degrees."""
    engine = engine or get_engine()
    base = prepare_for_ocr(content)
    best = None
    for rotation in (0, 90, 180, 270):
        image = apply_rotation(base, rotation)
        lines = engine.recognise(image)
        if best is None or _quality(lines) > best[0]:
            best = (_quality(lines), rotation, image.shape, lines)
        if rotation == 0 and _good_enough(lines):
            break
    _, rotation, shape, lines = best
    lines = reading_order(lines)
    return {
        "engine": engine.name, "engine_version": getattr(engine, "version", "unknown"), "rotation": rotation,
        "image_width": shape[1], "image_height": shape[0], "lines": lines,
        "mean_confidence": sum(l.confidence for l in lines) / len(lines) if lines else 0.0,
    }

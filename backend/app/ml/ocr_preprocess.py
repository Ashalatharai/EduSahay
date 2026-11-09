"""OpenCV preparation for OCR: decode, rescale, straighten small skew, boost contrast. No PaddleOCR needed."""
import cv2
import numpy as np

from app.ml.errors import UnreadableImage

MIN_SIDE, MAX_SIDE = 1200, 2200


def decode_color(content: bytes) -> np.ndarray:
    """BGR image from JPG/PNG (EXIF orientation honoured) or the first page of a PDF."""
    if content[:4] == b"%PDF":
        try:
            import fitz

            with fitz.open(stream=content, filetype="pdf") as pdf:
                pix = pdf[0].get_pixmap(dpi=200, colorspace=fitz.csRGB)
                rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, : pix.width * 3]
                return cv2.cvtColor(rgb.reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise UnreadableImage("The PDF could not be read") from e
    img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise UnreadableImage("The image could not be read")
    return img


def estimate_skew(gray: np.ndarray, max_angle: float = 10.0, step: float = 0.5) -> float:
    """Angle (degrees, OpenCV convention) to rotate by to straighten the page; 0 if there is no clear skew.
    Picks the angle whose horizontal projection profile is sharpest (text rows and table lines line up)."""
    scale = 600 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    bw = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h, w = bw.shape
    scores = {}
    for a in np.arange(-max_angle, max_angle + 1e-9, step):
        rotated = cv2.warpAffine(bw, cv2.getRotationMatrix2D((w / 2, h / 2), float(a), 1.0), (w, h))
        profile = rotated.sum(axis=1, dtype=np.float64)
        scores[float(a)] = float(np.sum(np.diff(profile) ** 2))
    best = max(scores, key=scores.get)
    return best if scores[best] > scores[0.0] * 1.02 else 0.0


def prepare_for_ocr(content: bytes, rotation: int = 0) -> np.ndarray:
    """Deterministic: the same bytes and rotation always give the same image, so OCR boxes can be reused later
    (Phase 6 feeds this same image and its boxes to LayoutLMv3). `rotation` is a clockwise multiple of 90."""
    img = decode_color(content)
    side = max(img.shape[:2])
    if side < MIN_SIDE or side > MAX_SIDE:
        scale = (MIN_SIDE if side < MIN_SIDE else MAX_SIDE) / side
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    angle = estimate_skew(gray)
    if angle:
        h, w = gray.shape
        gray = cv2.warpAffine(gray, cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0), (w, h),
                              flags=cv2.INTER_CUBIC, borderValue=255)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    out = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return apply_rotation(out, rotation)


def apply_rotation(img: np.ndarray, rotation: int) -> np.ndarray:
    code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}.get(rotation % 360)
    return img if code is None else cv2.rotate(img, code)

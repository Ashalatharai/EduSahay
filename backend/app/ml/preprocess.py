"""OpenCV preprocessing shared by training and inference. Works on file CONTENT only, never the filename."""
import cv2
import numpy as np

from app.ml.errors import UnreadableImage

IMG_SIZE = 128


def decode(content: bytes) -> np.ndarray:
    """Return a grayscale uint8 image. PDFs are detected by signature and rendered (first page)."""
    if content[:4] == b"%PDF":
        try:
            import fitz  # PyMuPDF

            with fitz.open(stream=content, filetype="pdf") as pdf:
                pix = pdf[0].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
                return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, : pix.width].copy()
        except Exception as e:
            raise UnreadableImage("The PDF could not be read") from e
    img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        raise UnreadableImage("The image could not be read")
    return img


def preprocess(gray: np.ndarray) -> np.ndarray:
    """Contrast-normalise, resize keeping aspect ratio (white padding), scale to [-1, 1]. Returns (1, H, W) float32."""
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    h, w = gray.shape
    scale = IMG_SIZE / max(h, w)
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    small = cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((IMG_SIZE, IMG_SIZE), 255, np.uint8)
    y, x = (IMG_SIZE - nh) // 2, (IMG_SIZE - nw) // 2
    canvas[y : y + nh, x : x + nw] = small
    return ((canvas.astype(np.float32) / 255.0 - 0.5) / 0.5)[None]

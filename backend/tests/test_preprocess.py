import sys
from pathlib import Path

import numpy as np
import pytest

from app.ml.errors import UnreadableImage
from app.ml.preprocess import IMG_SIZE, decode, preprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "classifier"))
import make_synthetic_dataset as gen  # noqa: E402


def test_preprocess_image_and_pdf(tmp_path):
    gen.generate(tmp_path, {"train": 2}, seed=1)
    assert sorted(p.name for p in (tmp_path / "train").iterdir()) == sorted(gen.LABELS)
    png = (tmp_path / "train" / "sslc" / "0000.png").read_bytes()
    x = preprocess(decode(png))
    assert x.shape == (1, IMG_SIZE, IMG_SIZE) and x.dtype == np.float32 and -1.0 <= x.min() and x.max() <= 1.0

    import fitz

    pdf = fitz.open(); page = pdf.new_page(); page.insert_text((72, 72), "hello")
    assert decode(pdf.tobytes()).ndim == 2

    with pytest.raises(UnreadableImage):
        decode(b"\xff\xd8\xff not really a jpeg")
    with pytest.raises(UnreadableImage):
        decode(b"%PDF-1.4 broken")
    assert preprocess(np.full((1, 1), 200, np.uint8)).shape == (1, IMG_SIZE, IMG_SIZE)

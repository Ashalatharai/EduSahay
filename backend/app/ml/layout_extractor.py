"""LayoutLMv3 token classification inference. Needs a FINE-TUNED checkpoint (see ml/extraction/README.md)."""
import json
from functools import lru_cache
from pathlib import Path

import cv2
import torch
from PIL import Image

from app.core.config import settings
from app.ml.errors import ModelNotAvailable
from app.ml.extraction_schema import ID2LABEL


class LayoutExtractor:
    def __init__(self, model_dir: str):
        d = Path(model_dir)
        if not (d / "config.json").exists():
            raise ModelNotAvailable("The LayoutLMv3 extractor has not been fine-tuned yet")
        from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3ImageProcessor, LayoutLMv3TokenizerFast

        self.tokenizer = LayoutLMv3TokenizerFast.from_pretrained(d)
        self.image_processor = LayoutLMv3ImageProcessor.from_pretrained(d, apply_ocr=False)
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(d).eval()
        self.meta = json.loads((d / "extractor_meta.json").read_text()) if (d / "extractor_meta.json").exists() else {}
        self.version = f"layoutlmv3-{self.meta.get('trained_at', 'unknown')[:10]}"

    @property
    def prototype(self) -> bool:
        """True when trained only on synthetic data: results show the pipeline works, not real-world accuracy."""
        return self.meta.get("dataset_type", "unknown") != "real"

    @torch.no_grad()
    def predict_words(self, image_bgr, words: list[str], boxes: list[list[int]]):
        """Returns (label, confidence) per input word. Boxes are pixels of image_bgr."""
        if not words:
            return [], []
        h, w = image_bgr.shape[:2]
        norm = [[max(0, min(1000, int(1000 * b[0] / w))), max(0, min(1000, int(1000 * b[1] / h))),
                 max(0, min(1000, int(1000 * b[2] / w))), max(0, min(1000, int(1000 * b[3] / h)))] for b in boxes]
        enc = self.tokenizer(words, boxes=norm, truncation=True, max_length=512, padding="max_length", return_tensors="pt")
        pix = self.image_processor(Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)), return_tensors="pt")["pixel_values"]
        logits = self.model(input_ids=enc["input_ids"], bbox=enc["bbox"], attention_mask=enc["attention_mask"], pixel_values=pix).logits[0]
        probs = torch.softmax(logits, dim=-1)
        labels, confs = ["O"] * len(words), [1.0] * len(words)
        seen = set()
        for tok, wid in enumerate(enc.word_ids(0)):
            if wid is not None and wid not in seen:  # first sub-token of each word
                seen.add(wid)
                k = int(probs[tok].argmax())
                labels[wid], confs[wid] = ID2LABEL[k], float(probs[tok][k])
        return labels, confs


@lru_cache(maxsize=1)
def get_extractor() -> LayoutExtractor:
    try:
        return LayoutExtractor(settings.extractor_dir)
    except ImportError as e:
        raise ModelNotAvailable("transformers/PyTorch are not installed") from e

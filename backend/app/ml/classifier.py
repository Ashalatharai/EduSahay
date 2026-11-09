"""CNN document classifier (PyTorch). Weights come from training on a labelled dataset; nothing is hardcoded."""
import hashlib
from functools import lru_cache
from pathlib import Path

import torch
from torch import nn

from app.core.config import settings
from app.ml.errors import ModelNotAvailable
from app.ml.preprocess import IMG_SIZE, decode, preprocess

LABELS = ["aadhaar", "sslc", "puc", "other"]


class DocCNN(nn.Module):
    def __init__(self, n_classes: int = len(LABELS)):
        super().__init__()

        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))

        self.features = nn.Sequential(block(1, 16), block(16, 32), block(32, 64), block(64, 128))
        # a 4x4 grid keeps coarse layout information (where tables, photos and headers sit)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(4), nn.Flatten(), nn.Dropout(0.3), nn.Linear(128 * 16, n_classes))

    def forward(self, x):
        return self.head(self.features(x))


def save_checkpoint(model: nn.Module, path, meta: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "labels": LABELS, "img_size": IMG_SIZE, "meta": meta}, path)


class DocumentClassifier:
    def __init__(self, path: str):
        if not Path(path).exists():
            raise ModelNotAvailable("The document classifier has not been trained yet")
        ckpt = torch.load(path, map_location="cpu", weights_only=True)
        if ckpt["labels"] != LABELS or ckpt["img_size"] != IMG_SIZE:
            raise ModelNotAvailable("The classifier checkpoint does not match this code version")
        self.model = DocCNN()
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.meta = ckpt["meta"]
        self.version = "cnn-" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]

    @torch.no_grad()
    def predict(self, content: bytes) -> dict:
        x = torch.from_numpy(preprocess(decode(content)))[None]
        probs = torch.softmax(self.model(x), dim=1)[0]
        i = int(probs.argmax())
        return {
            "label": LABELS[i],
            "confidence": float(probs[i]),
            "probabilities": {l: float(p) for l, p in zip(LABELS, probs)},
        }


@lru_cache(maxsize=1)
def get_classifier() -> DocumentClassifier:
    return DocumentClassifier(settings.classifier_path)

"""Train the CNN document classifier. Usage: python train.py --data ../datasets/classifier"""
import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.config import settings  # noqa: E402
from app.ml.classifier import LABELS, DocCNN, save_checkpoint  # noqa: E402
from app.ml.preprocess import preprocess  # noqa: E402


class FolderDataset(Dataset):
    def __init__(self, root, augment=False):
        self.items = [(p, i) for i, l in enumerate(LABELS) for p in sorted((Path(root) / l).glob("*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
        self.augment = augment

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, label = self.items[i]
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if self.augment:
            h, w = img.shape
            M = cv2.getRotationMatrix2D((w / 2, h / 2), random.uniform(-3, 3), random.uniform(0.95, 1.05))
            img = cv2.warpAffine(img, M, (w, h), borderValue=255)
            img = np.clip(img.astype(np.float32) * random.uniform(0.85, 1.1) + random.uniform(-15, 15), 0, 255).astype(np.uint8)
        return torch.from_numpy(preprocess(img)), label


def accuracy(model, loader):
    model.eval(); correct = n = 0
    with torch.no_grad():
        for x, y in loader:
            correct += (model(x).argmax(1) == y).sum().item(); n += len(y)
    return correct / max(n, 1)


def train(data_dir, out_path=None, epochs=12, batch=32, lr=1e-3, seed=0):
    data_dir = Path(data_dir); out_path = out_path or settings.classifier_path
    torch.manual_seed(seed); random.seed(seed)
    tr = DataLoader(FolderDataset(data_dir / "train", augment=True), batch_size=batch, shuffle=True)
    va = DataLoader(FolderDataset(data_dir / "val"), batch_size=batch)
    model = DocCNN(); opt = torch.optim.Adam(model.parameters(), lr=lr); loss_fn = nn.CrossEntropyLoss()
    ds_meta = json.loads((data_dir / "meta.json").read_text()) if (data_dir / "meta.json").exists() else {}
    best = -1.0
    for ep in range(1, epochs + 1):
        model.train(); total = 0.0
        for x, y in tr:
            opt.zero_grad(); loss = loss_fn(model(x), y); loss.backward(); opt.step(); total += loss.item() * len(y)
        val = accuracy(model, va)
        print(f"epoch {ep:02d}  train_loss {total / len(tr.dataset):.4f}  val_acc {val:.3f}", flush=True)
        if val >= best:
            best = val
            save_checkpoint(model, out_path, {"dataset_type": ds_meta.get("type", "unknown"), "epochs": epochs,
                                              "best_val_accuracy": float(val), "trained_at": datetime.now(timezone.utc).isoformat()})
    return best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../datasets/classifier"); ap.add_argument("--out", default=None)
    ap.add_argument("--epochs", type=int, default=12)
    a = ap.parse_args()
    best = train(a.data, a.out, a.epochs)
    print(f"Saved best checkpoint (validation accuracy {best:.3f}) to {a.out or settings.classifier_path}")

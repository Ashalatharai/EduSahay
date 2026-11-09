"""Fine-tune LayoutLMv3 for token classification.

Usage: python train.py --data ../datasets/extraction [--epochs 8]
Needs `transformers` and PyTorch, and downloads microsoft/layoutlmv3-base (pretrained weights) on first run.
A GPU is strongly recommended; on CPU use a small --epochs and dataset.
"""
import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader
from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.config import settings  # noqa: E402
from app.ml.extraction_schema import ID2LABEL, LABEL2ID, LABELS  # noqa: E402

BASE = "microsoft/layoutlmv3-base"


def load_split(root: Path, processor):
    items = []
    for line in (root / "annotations.jsonl").read_text().splitlines():
        rec = json.loads(line)
        w, h = rec["width"], rec["height"]
        boxes = [[max(0, min(1000, int(1000 * b[0] / w))), max(0, min(1000, int(1000 * b[1] / h))),
                  max(0, min(1000, int(1000 * b[2] / w))), max(0, min(1000, int(1000 * b[3] / h)))] for b in rec["boxes"]]
        enc = processor(Image.open(root / rec["image"]).convert("RGB"), rec["words"], boxes=boxes,
                        word_labels=[LABEL2ID[l] for l in rec["labels"]], truncation=True, padding="max_length",
                        max_length=512, return_tensors="pt")
        items.append({k: v.squeeze(0) for k, v in enc.items()})
    return items


def token_accuracy(model, items, device):
    model.eval(); correct = total = 0
    with torch.no_grad():
        for b in DataLoader(items, batch_size=2):
            b = {k: v.to(device) for k, v in b.items()}
            pred = model(**{k: v for k, v in b.items() if k != "labels"}).logits.argmax(-1)
            mask = b["labels"] != -100
            correct += ((pred == b["labels"]) & mask).sum().item(); total += mask.sum().item()
    return correct / max(total, 1)


def train(data_dir, out_dir=None, epochs=8, batch=2, lr=5e-5, seed=0):
    data_dir, out_dir = Path(data_dir), Path(out_dir or settings.extractor_dir)
    random.seed(seed); torch.manual_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = LayoutLMv3Processor.from_pretrained(BASE, apply_ocr=False)
    tr, va = load_split(data_dir / "train", processor), load_split(data_dir / "val", processor)
    model = LayoutLMv3ForTokenClassification.from_pretrained(BASE, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    best = -1.0
    for ep in range(1, epochs + 1):
        model.train(); total = 0.0
        for b in DataLoader(tr, batch_size=batch, shuffle=True):
            opt.zero_grad(); loss = model(**{k: v.to(device) for k, v in b.items()}).loss; loss.backward(); opt.step(); total += loss.item()
        acc = token_accuracy(model, va, device)
        print(f"epoch {ep:02d}  loss {total / max(len(tr) / batch, 1):.4f}  val_token_acc {acc:.3f}", flush=True)
        if acc >= best:
            best = acc
            model.save_pretrained(out_dir); processor.save_pretrained(out_dir)
            meta = json.loads((data_dir / "meta.json").read_text()) if (data_dir / "meta.json").exists() else {}
            (out_dir / "extractor_meta.json").write_text(json.dumps({
                "dataset_type": meta.get("type", "unknown"), "base_model": BASE, "epochs": epochs,
                "best_val_token_accuracy": best, "trained_at": datetime.now(timezone.utc).isoformat()}, indent=2))
    return best


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../datasets/extraction"); ap.add_argument("--out", default=None)
    ap.add_argument("--epochs", type=int, default=8)
    a = ap.parse_args()
    print(f"Best validation token accuracy {train(a.data, a.out, a.epochs):.3f}")

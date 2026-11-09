# LayoutLMv3 information extraction

```
pip install transformers torch            # plus backend/requirements.txt
cd ml/extraction
python make_extraction_dataset.py --out ../datasets/extraction   # fictional annotated documents
python train.py --data ../datasets/extraction                    # downloads microsoft/layoutlmv3-base, saves backend/models/layoutlmv3/
python evaluate.py --data ../datasets/extraction                 # field precision / recall / F1
```
Labels are BIO tags over 12 entities (see `backend/app/ml/extraction_schema.py`). The model is only used once it has
been fine-tuned: the base pretrained weights have no extraction head and are never used for results.
A model trained on the synthetic data is reported as a **prototype** in the API and UI.

To use real documents, annotate authorized, consented scans in the same JSONL format
(`words`, `boxes` in pixels, `labels`, `width`, `height`) and set `"type": "real"` in `meta.json`.

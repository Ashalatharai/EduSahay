# PaddleOCR evaluation

OCR is not trained here: the app uses pretrained PaddleOCR (text detection + recognition). This folder only measures it.

```
pip install paddlepaddle paddleocr        # install the PaddlePaddle runtime for your platform first if needed
cd ml/extraction
python make_extraction_dataset.py --out ../datasets/extraction    # fictional annotated documents (known words)
cd ../ocr
python evaluate.py --data ../datasets/extraction                  # CER / WER, overall and per document type
python evaluate.py --data ../datasets/extraction --limit 20       # quick run
```
The reference text is the known word list of each synthetic document, joined in reading order. The hypothesis is the
OCR output for the same page after the app's own preprocessing (`backend/app/ml/ocr_preprocess.py`). Reports are written
to `ml/evaluation/reports/`. PaddleOCR downloads its models on first run, so the first run needs internet access.

The documents are synthetic, so CER and WER here show that the pipeline works, not how it performs on real scans.
To measure real accuracy, add authorized, consented scans with hand-typed reference words in the same `annotations.jsonl`
format used by `ml/extraction/README.md`.

# CNN document classifier

```
cd ml/classifier
python make_synthetic_dataset.py --out ../datasets/classifier    # fictional data
python train.py --data ../datasets/classifier                    # saves backend/models/doc_classifier.pt
python evaluate.py --data ../datasets/classifier                 # accuracy, precision, recall, F1, confusion matrix
python predict.py some_scan.png
```
The synthetic layouts are invented and the classes are easy to separate, so scores on this data
say little about real documents. For real use, add authorized, consented scans under
`train/ val/ test/ {aadhaar,sslc,puc,other}/` and retrain. Reports are written to `ml/evaluation/reports/`.
Predictions below `CLASSIFIER_MIN_CONFIDENCE` (default 0.6), or labelled `other`, are treated as unsupported.

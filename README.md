# Edu Sahaya
Deep Learning-based student admission document intelligence and automated form generation.
*Simplifying Admissions Through Intelligent Document Processing.*

Students upload Aadhaar, SSLC and PUC documents. A CNN identifies each document, PaddleOCR reads the text, LayoutLMv3
extracts the fields, cross-document checks flag problems, and an admission form is prefilled for the student to review
and submit. Administrators review applications, check possible duplicates, approve or request corrections, and a PDF
admission profile is generated.

## Run
```
docker compose up -d                              # PostgreSQL
cp backend/.env.example backend/.env              # set SECRET_KEY, ENCRYPTION_KEY, ADMIN_EMAIL, ADMIN_PASSWORD

cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                   # install the PaddlePaddle runtime for your platform first if needed
pytest                                            # backend tests
uvicorn app.main:app --reload                     # http://localhost:8000/docs

cd frontend && npm install && npm run dev         # http://localhost:5173
```
Tables are created on startup (`create_all`). If you ran an earlier phase's database, drop it first: new columns and tables were added.

## Train the models (each folder has its own README)
```
cd ml/classifier && python make_synthetic_dataset.py && python train.py && python evaluate.py     # CNN
cd ml/extraction && python make_extraction_dataset.py && python train.py && python evaluate.py    # LayoutLMv3
cd ml/ocr && python evaluate.py                                                                    # PaddleOCR CER / WER
cd ml/evaluation && python run_all.py                                                              # everything available
```
Until a model exists, the app keeps working: uploads succeed and that stage is skipped (documents stay unclassified, or
details must be typed into the form). Datasets generated here are **synthetic and fictional**, so models trained on them
are prototypes and the app labels them as such. Use authorized, consented real documents for real accuracy.

## Automatic admission form
After upload, OCR and LayoutLMv3 results are mapped onto the admission form (`backend/app/services/form.py`), so the form opens already filled
and keeps refreshing while documents are still being read (typed edits are preserved). Missing, incorrect and low-confidence fields are
highlighted with a reason, the student confirms, and `Download Admission Form` produces a PDF (`GET /api/applications/me/form.pdf`,
`services/form_pdf.py`). Before submission the PDF is marked DRAFT; after submission it prints the submitted values. Values that are not
known print as a dash, nothing is invented. Once all three documents are processed the cross-document checks run automatically.

## Layout
- `frontend/` React + Vite + Tailwind. `backend/app/` FastAPI: `api` routes, `services` logic, `ml` model inference (separate from routing)
- `ml/` dataset preparation, training, evaluation. `storage/` encrypted uploads (never served publicly)

## Privacy and limits
Documents are encrypted at rest, served only through authenticated endpoints, and Aadhaar numbers are masked before
anything is stored. Registration records consent. Validation is a preliminary consistency check between a student's own
documents; it is **not** Aadhaar authentication or government verification.

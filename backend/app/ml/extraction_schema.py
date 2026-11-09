"""Field labels for LayoutLMv3 token classification (BIO scheme) and the fields each document type yields."""
ENTITIES = ["NAME", "DOB", "GENDER", "AADHAAR_NO", "REG_NO", "SCHOOL", "COLLEGE", "YEAR", "SUBJECT", "MARKS", "TOTAL", "PERCENT"]
LABELS = ["O"] + [f"{p}-{e}" for e in ENTITIES for p in "BI"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}

SINGLE_FIELDS = {
    "aadhaar": {"NAME": "student_name", "DOB": "date_of_birth", "GENDER": "gender", "AADHAAR_NO": "aadhaar_number_masked"},
    "sslc": {"NAME": "student_name", "REG_NO": "register_number", "DOB": "date_of_birth", "SCHOOL": "school_name",
             "YEAR": "exam_year", "TOTAL": "total_marks", "PERCENT": "percentage"},
    "puc": {"NAME": "student_name", "REG_NO": "register_number", "COLLEGE": "college_name", "YEAR": "exam_year",
            "TOTAL": "total_marks", "PERCENT": "percentage"},
}
HAS_SUBJECTS = {"sslc", "puc"}


def allowed_field(doc_type: str, name: str) -> bool:
    import re

    if doc_type == "admission_form":
        return True
    if name in SINGLE_FIELDS.get(doc_type, {}).values():
        return True
    return doc_type in HAS_SUBJECTS and re.fullmatch(r"subject_\d{1,2}_(name|marks)", name) is not None

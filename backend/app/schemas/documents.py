from datetime import datetime

from pydantic import BaseModel


class ClassificationOut(BaseModel):
    predicted_label: str
    confidence: float
    model_version: str
    recognised: bool

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    slot: str
    original_name: str
    mime_type: str
    size_bytes: int
    status: str
    uploaded_at: datetime
    classification: ClassificationOut | None = None
    slot_matches: bool | None = None

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: int
    status: str
    submitted_at: datetime | None = None
    review_decision: str | None = None
    review_comment: str | None = None

    model_config = {"from_attributes": True}


class OcrLineOut(BaseModel):
    text: str
    confidence: float
    box: list[list[int]]


class OcrResultOut(BaseModel):
    engine: str
    engine_version: str
    rotation: int
    image_width: int
    image_height: int
    mean_confidence: float
    lines: list[OcrLineOut]

    model_config = {"from_attributes": True}


class FieldOut(BaseModel):
    field_name: str
    value: str | None
    original_value: str | None
    confidence: float | None
    needs_review: bool
    source: str


class FieldsOut(BaseModel):
    model: dict | None  # None until a model has produced results; prototype=True means trained on synthetic data
    fields: list[FieldOut]


class FieldUpdate(BaseModel):
    value: str


class ValidationItem(BaseModel):
    field_name: str
    status: str  # matched | mismatch | missing | needs_review
    detail: str | None


class ValidationOut(BaseModel):
    summary: dict[str, int]
    results: list[ValidationItem]
    disclaimer: str


class FormField(BaseModel):
    key: str
    label: str
    section: str
    required: bool
    value: str | None
    source: str  # documents | account | manual | edited
    needs_review: bool
    error: str | None = None  # why the current value is missing or incorrect


class FormOut(BaseModel):
    status: str
    editable: bool
    fields: list[FormField]


class FormSave(BaseModel):
    values: dict[str, str | None]


class SubmitIn(BaseModel):
    confirm: bool


class AutoFormField(BaseModel):
    field_id: str
    label: str
    section: str = "personal"
    page: int = 0
    matched_key: str | None = None
    value: str | None = None
    suggested_value: str | None = None
    confidence: float = 0.9
    field_type: str = "text"
    is_edited: bool = False


class AutoFormDocument(BaseModel):
    id: int
    original_name: str
    mime_type: str


class AutoFormOut(BaseModel):
    status: str
    document: AutoFormDocument | None = None
    fields: list[AutoFormField] = []
    pages_count: int = 0
    updated_at: str | None = None
    message: str | None = None


class AutoFormSave(BaseModel):
    edits: dict[str, str]

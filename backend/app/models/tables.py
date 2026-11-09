"""The nine core tables. Sensitive values (e.g. Aadhaar) are stored masked only."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, UniqueConstraint, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.session import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    profile: Mapped["StudentProfile | None"] = relationship(back_populates="user", uselist=False)
    applications: Mapped[list["AdmissionApplication"]] = relationship(back_populates="user")
    documents: Mapped[list["UploadedDocument"]] = relationship(back_populates="user")


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    user: Mapped[User] = relationship(back_populates="profile")


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slot: Mapped[str] = mapped_column(String(20))  # aadhaar | sslc | puc
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))  # private, encrypted at rest (Phase 3)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="documents")
    classifications: Mapped[list["DocumentClassificationResult"]] = relationship(
        order_by="DocumentClassificationResult.id.desc()")

    @property
    def classification(self):
        return self.classifications[0] if self.classifications else None

    @property
    def slot_matches(self) -> bool | None:
        c = self.classification
        return None if c is None else (c.recognised and c.predicted_label == self.slot)


class DocumentClassificationResult(Base):
    __tablename__ = "document_classification_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("uploaded_documents.id"), index=True)
    predicted_label: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    @property
    def recognised(self) -> bool:
        """A supported type AND confident enough; otherwise treated as an unsupported document."""
        return self.predicted_label != "other" and self.confidence >= settings.classifier_min_confidence


class OcrResult(Base):
    """OCR output for one document. Boxes are in pixels of the preprocessed image (see ml/ocr_preprocess.py)."""
    __tablename__ = "ocr_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("uploaded_documents.id"), unique=True)
    engine: Mapped[str] = mapped_column(String(30))
    engine_version: Mapped[str] = mapped_column(String(30))
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    mean_confidence: Mapped[float] = mapped_column(Float)
    lines: Mapped[list] = mapped_column(JSON)  # [{text (Aadhaar masked), confidence, box}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExtractedInformation(Base):
    __tablename__ = "extracted_information"
    __table_args__ = (UniqueConstraint("document_id", "field_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("uploaded_documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(60))
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[list | None] = mapped_column(JSON)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="model")  # model | manual

    @property
    def current_value(self):
        return self.corrected_value if self.corrected_value is not None else self.value


class AdmissionApplication(Base):
    __tablename__ = "admission_applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="documents_not_uploaded")
    form_data: Mapped[dict | None] = mapped_column(JSON)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    user: Mapped[User] = relationship(back_populates="applications")
    auto_filled_form: Mapped["AutoFilledForm | None"] = relationship(back_populates="application", uselist=False)


class AutoFilledForm(Base):
    __tablename__ = "auto_filled_forms"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("admission_applications.id"), unique=True, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_documents.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending | processing | ready | error
    fields_data: Mapped[list | None] = mapped_column(JSON)
    edits: Mapped[dict | None] = mapped_column(JSON)
    stored_pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    application: Mapped[AdmissionApplication] = relationship(back_populates="auto_filled_form")


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("admission_applications.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))  # matched | mismatch | missing | needs_review
    detail: Mapped[str | None] = mapped_column(Text)


class DuplicateDetectionResult(Base):
    __tablename__ = "duplicate_detection_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("admission_applications.id"), index=True)
    matched_application_id: Mapped[int] = mapped_column(ForeignKey("admission_applications.id"))
    similarity: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list | None] = mapped_column(JSON)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class AdminReview(Base):
    __tablename__ = "admin_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("admission_applications.id"), index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))  # approved | correction_requested
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

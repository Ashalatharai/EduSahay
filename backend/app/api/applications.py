from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models import AdminReview, User
from app.schemas.documents import (
    ApplicationOut,
    AutoFormOut,
    AutoFormSave,
    FormOut,
    FormSave,
    SubmitIn,
    ValidationOut,
)
from app.services import form as form_service
from app.services import form_filler
from app.services.form_pdf import build_admission_form_pdf
from app.services.pdf import build_profile_pdf
from app.services.duplicates import detect_duplicates
from app.services.applications import current_application
from app.services.validation import results_for, validate_application

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("/me", response_model=ApplicationOut)
def my_application(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    app = current_application(db, user)
    review = db.scalar(select(AdminReview).where(AdminReview.application_id == app.id).order_by(AdminReview.id.desc()))
    return {"id": app.id, "status": app.status, "submitted_at": app.submitted_at,
            "review_decision": review and review.decision, "review_comment": review and review.comments}


@router.post("/me/validate", response_model=ValidationOut)
def validate(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    return results_for(db, validate_application(db, user))


@router.get("/me/validation", response_model=ValidationOut)
def validation(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    return results_for(db, current_application(db, user))


def _editable(db, user):
    if not form_service.build_form(db, user)["editable"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This application can no longer be edited")


@router.get("/me/form", response_model=FormOut)
def get_form(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    return form_service.build_form(db, user)


@router.put("/me/form", response_model=FormOut)
def save_form(body: FormSave, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    _editable(db, user)
    try:
        return form_service.save_edits(db, user, body.values)
    except KeyError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown fields: {e.args[0]}")


@router.post("/me/submit", response_model=ApplicationOut)
def submit_application(body: SubmitIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    _editable(db, user)
    if not body.confirm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please confirm that the details are correct")
    missing = form_service.missing_documents(db, user)
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Upload all documents first. Missing: {', '.join(missing)}")
    values = {f["key"]: f["value"] for f in form_service.build_form(db, user)["fields"]}
    errors = form_service.validate_values(values)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "; ".join(errors.values()))
    validate_application(db, user)  # record the latest checks for the administrator
    app = form_service.submit(db, user)
    detect_duplicates(db, app)  # flags possible duplicates for the administrator; never rejects
    return app


@router.get("/me/profile.pdf")
def profile_pdf(download: bool = False, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    app = current_application(db, user)
    if app.status not in ("submitted", "approved"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Submit your application to generate the admission profile")
    return Response(build_profile_pdf(db, app), media_type="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="edu-sahaya-admission-profile.pdf"',
        "Cache-Control": "no-store"})


@router.get("/me/form.pdf")
def admission_form_pdf(download: bool = False, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """The admission form as a PDF. Before submission it is a draft built from the current form; afterwards, the submitted values."""
    app = current_application(db, user)
    return Response(build_admission_form_pdf(db, app), media_type="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="edu-sahaya-admission-form.pdf"',
        "Cache-Control": "no-store"})


@router.get("/me/auto-form", response_model=AutoFormOut)
def get_auto_filled_form(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """Returns detected fields and auto-filled values from the uploaded blank college admission form."""
    return form_filler.get_auto_form(db, user)


@router.put("/me/auto-form", response_model=AutoFormOut)
def update_auto_filled_form(body: AutoFormSave, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """Saves student edits/corrections to the auto-filled admission form and re-renders it."""
    _editable(db, user)
    return form_filler.save_auto_form_edits(db, user, body.edits)


@router.get("/me/auto-form/preview/{page_no}")
def preview_auto_filled_form(page_no: int = 0, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """Renders a PNG preview of the filled admission form page for live browser review."""
    try:
        png_bytes = form_filler.get_auto_form_preview_image(db, user, page_no)
        return Response(png_bytes, media_type="image/png", headers={"Cache-Control": "no-store"})
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/me/auto-form/download")
def download_auto_filled_form(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """Downloads the completed filled college admission form as a PDF, preserving original design and layout."""
    try:
        pdf_bytes = form_filler.get_auto_form_pdf(db, user)
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="completed-admission-form.pdf"',
                "Cache-Control": "no-store",
            },
        )
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

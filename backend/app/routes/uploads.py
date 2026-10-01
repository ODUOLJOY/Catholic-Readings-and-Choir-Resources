from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.database import get_db
from app.models.choir import ChoirResource
from app.models.parish import Parish
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services.authorization import manageable_choir_parish_ids

router = APIRouter(
    prefix="/api/uploads",
    tags=["Uploads"],
)

# ==============================
# CONFIGURATION
# ==============================

UPLOAD_DIR = Path("media")
PRIVATE_UPLOAD_DIR = Path(settings.STORAGE_PATH) / "private_media"

IMAGE_DIR = UPLOAD_DIR / "images"
PDF_DIR = UPLOAD_DIR / "pdfs"
AUDIO_DIR = UPLOAD_DIR / "audio"
VIDEO_DIR = UPLOAD_DIR / "videos"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE = settings.MAX_IMAGE_SIZE
MAX_PDF = settings.MAX_DOCUMENT_SIZE
MAX_AUDIO = settings.MAX_AUDIO_SIZE
MAX_VIDEO = settings.MAX_VIDEO_SIZE


def get_destination(filename: str):
    ext = filename.split(".")[-1].lower()

    image_types = {item.strip().lower() for item in settings.ALLOWED_IMAGE_TYPES.split(",")}
    document_types = {
        item.strip().lower() for item in settings.ALLOWED_DOCUMENT_TYPES.split(",")
    }
    audio_types = {item.strip().lower() for item in settings.ALLOWED_AUDIO_TYPES.split(",")}
    video_types = {item.strip().lower() for item in settings.ALLOWED_VIDEO_TYPES.split(",")}

    if ext in image_types:
        return IMAGE_DIR, MAX_IMAGE

    if ext in document_types:
        return PDF_DIR, MAX_PDF

    if ext in audio_types:
        return AUDIO_DIR, MAX_AUDIO

    if ext in video_types:
        return VIDEO_DIR, MAX_VIDEO

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type.",
    )


@router.get("/scopes")
def upload_scopes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parish_ids = manageable_choir_parish_ids(db, current_user)
    parishes = (
        db.query(Parish.id, Parish.name)
        .filter(Parish.id.in_(parish_ids))
        .order_by(Parish.name)
        .all()
        if parish_ids
        else []
    )
    return {
        "parishes": [{"id": parish_id, "name": name} for parish_id, name in parishes],
    }


# ==============================
# UPLOAD RESOURCE
# ==============================

@router.post("/")
async def upload_resource(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(None),
    language: str = Form("English"),
    parish_id: int | None = Form(None),
    global_scope: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename_suffix = Path(file.filename or "").suffix.lower()
    _, max_size = get_destination(filename_suffix.lstrip("."))

    allowed_parishes = manageable_choir_parish_ids(db, current_user)
    if global_scope and parish_id is not None:
        raise HTTPException(status_code=400, detail="Select only one resource scope.")
    if parish_id is None and not global_scope and current_user.role != "super_admin":
        if len(allowed_parishes) == 1:
            parish_id = allowed_parishes[0]
        elif len(allowed_parishes) > 1:
            raise HTTPException(
                status_code=400,
                detail="Choose a parish scope before submitting this resource.",
            )
    if parish_id is not None and parish_id not in allowed_parishes:
        raise HTTPException(
            status_code=403,
            detail="You cannot submit resources to this parish.",
        )

    extension = filename_suffix.lstrip(".")
    scoped = parish_id is not None
    staging_dir = PRIVATE_UPLOAD_DIR / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    filepath = staging_dir / f"{uuid4().hex}.{extension}"

    file_size = 0
    try:
        with filepath.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > max_size:
                    raise HTTPException(
                        status_code=400,
                        detail="File exceeds maximum allowed size.",
                    )
                destination.write(chunk)
    except HTTPException:
        filepath.unlink(missing_ok=True)
        raise
    except OSError:
        filepath.unlink(missing_ok=True)
        raise

    resource = ChoirResource(
        title=title,
        description=description,
        category=category,
        language=language,
        file_url="/api/choir/pending/file",
        file_type=extension,
        file_size=file_size,
        uploaded_by=current_user.id,
        parish_id=parish_id,
        is_approved=False,
        is_published=False,
    )

    final_filepath: Path | None = None
    try:
        db.add(resource)
        db.flush()
        final_filepath = (
            PRIVATE_UPLOAD_DIR / "parishes" / str(parish_id)
            / f"{resource.id}.{extension}"
            if scoped
            else PRIVATE_UPLOAD_DIR / "resources" / f"{resource.id}.{extension}"
        )
        final_filepath.parent.mkdir(parents=True, exist_ok=True)
        resource.file_url = f"{str(request.base_url).rstrip('/')}/api/choir/{resource.id}/file"
        filepath.replace(final_filepath)
        db.commit()
        db.refresh(resource)
    except (SQLAlchemyError, OSError):
        db.rollback()
        filepath.unlink(missing_ok=True)
        if final_filepath is not None:
            final_filepath.unlink(missing_ok=True)
        raise

    return {
        "message": "Upload successful.",
        "resource": resource,
    }


# ==============================
# LIST FILES
# ==============================

@router.get("/")
def list_uploads(
    db: Session = Depends(get_db),
):
    return (
        db.query(ChoirResource)
        .filter(
            ChoirResource.is_approved == True,
            ChoirResource.is_published == True,
            ChoirResource.parish_id.is_(None),
        )
        .order_by(ChoirResource.created_at.desc())
        .all()
    )


# ==============================
# DELETE
# ==============================

@router.delete("/{resource_id}")
def delete_upload(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = (
        db.query(ChoirResource)
        .filter(ChoirResource.id == resource_id)
        .first()
    )

    if not resource:
        raise HTTPException(
            status_code=404,
            detail="Resource not found.",
        )

    from app.services.authorization import can_manage_choir_resource_scope

    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(status_code=403, detail="You cannot manage this resource.")

    from app.services.choir_resources import local_resource_file

    file_path = local_resource_file(resource)

    try:
        db.delete(resource)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    if file_path and file_path.exists():
        file_path.unlink()

    return {
        "message": "Resource deleted successfully."
    }
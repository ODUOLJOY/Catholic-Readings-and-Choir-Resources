import logging
import mimetypes
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
from app.constants.choir_categories import normalize_category
from app.models.parish import Parish
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services.authorization import manageable_choir_parish_ids
from app.services.file_signatures import SIGNATURE_CHECK_BYTES, valid_file_signature
from app.services.private_storage import (
    open_resource_file,
    put_private_file,
    remove_resource_file,
    resource_storage_key,
)

router = APIRouter(
    prefix="/api/uploads",
    tags=["Uploads"],
)
logger = logging.getLogger(__name__)

# ==============================
# CONFIGURATION
# ==============================

PRIVATE_UPLOAD_DIR = Path(settings.STORAGE_PATH) / "private_media"

MAX_IMAGE = settings.MAX_IMAGE_SIZE
MAX_PDF = settings.MAX_DOCUMENT_SIZE
MAX_AUDIO = settings.MAX_AUDIO_SIZE
MAX_VIDEO = settings.MAX_VIDEO_SIZE


def get_max_size(filename: str) -> int:
    ext = filename.split(".")[-1].lower()

    image_types = {item.strip().lower() for item in settings.ALLOWED_IMAGE_TYPES.split(",")}
    document_types = {
        item.strip().lower() for item in settings.ALLOWED_DOCUMENT_TYPES.split(",")
    }
    audio_types = {item.strip().lower() for item in settings.ALLOWED_AUDIO_TYPES.split(",")}
    video_types = {item.strip().lower() for item in settings.ALLOWED_VIDEO_TYPES.split(",")}

    if ext in image_types:
        return MAX_IMAGE

    if ext in document_types:
        return MAX_PDF

    if ext in audio_types:
        return MAX_AUDIO

    if ext in video_types:
        return MAX_VIDEO

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type.",
    )


EXPECTED_MIME_TYPES = {
    "jpg": {"image/jpeg", "image/jpg"},
    "jpeg": {"image/jpeg", "image/jpg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "mp3": {"audio/mpeg", "audio/mp3"},
    "wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    "m4a": {"audio/mp4", "audio/x-m4a"},
    "aac": {"audio/aac", "audio/aacp", "audio/x-aac"},
    "mp4": {"video/mp4", "application/mp4"},
    "mov": {"video/quicktime"},
    "mkv": {"video/x-matroska", "application/x-matroska"},
}


def _validate_content_type(extension: str, content_type: str | None) -> None:
    declared = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    expected = EXPECTED_MIME_TYPES.get(extension, set())
    if declared and declared not in expected and declared != "application/octet-stream":
        raise HTTPException(status_code=400, detail="MIME type does not match the file extension.")


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
        "global_scope_allowed": current_user.role in {"admin", "super_admin"},
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

    # Structured metadata (all optional / backwards compatible).
    alternative_title: str = Form(None),
    author: str = Form(None),
    arranger: str = Form(None),
    voice_part: str = Form(None),
    season: str = Form(None),
    key_signature: str = Form(None),
    tempo: str = Form(None),
):
    filename_suffix = Path(file.filename or "").suffix.lower()
    extension = filename_suffix.lstrip(".")
    max_size = get_max_size(extension)
    _validate_content_type(extension, file.content_type)

    allowed_parishes = manageable_choir_parish_ids(db, current_user)
    can_submit_global = current_user.role in {"admin", "super_admin"}
    if global_scope and parish_id is not None:
        raise HTTPException(status_code=400, detail="Select only one resource scope.")
    if global_scope and not can_submit_global:
        raise HTTPException(
            status_code=403,
            detail="Only platform administrators can submit global resources.",
        )
    if parish_id is None and not global_scope:
        if len(allowed_parishes) == 1:
            parish_id = allowed_parishes[0]
        elif len(allowed_parishes) > 1:
            raise HTTPException(
                status_code=400,
                detail="Choose a parish scope before submitting this resource.",
            )
        else:
            raise HTTPException(
                status_code=403,
                detail="Choose an authorized parish scope or request parish upload access.",
            )
    if parish_id is not None and parish_id not in allowed_parishes:
        raise HTTPException(
            status_code=403,
            detail="You cannot submit resources to this parish.",
        )

    staging_dir = PRIVATE_UPLOAD_DIR / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    filepath = staging_dir / f"{uuid4().hex}.{extension}"

    file_size = 0
    header = bytearray()
    try:
        with filepath.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > max_size:
                    raise HTTPException(
                        status_code=400,
                        detail="File exceeds maximum allowed size.",
                    )
                if len(header) < SIGNATURE_CHECK_BYTES:
                    header.extend(
                        chunk[: SIGNATURE_CHECK_BYTES - len(header)]
                    )
                destination.write(chunk)
        if not valid_file_signature(extension, bytes(header)):
            raise HTTPException(
                status_code=400,
                detail="File content does not match the declared file type.",
            )
    except HTTPException:
        filepath.unlink(missing_ok=True)
        raise
    except OSError:
        filepath.unlink(missing_ok=True)
        raise

    category = normalize_category(category)

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
        alternative_title=alternative_title,
        author=author,
        arranger=arranger,
        voice_part=voice_part,
        season=season,
        key_signature=key_signature,
        tempo=tempo,
    )

    committed = False
    try:
        db.add(resource)
        db.flush()
        resource.storage_key = resource_storage_key(resource)
        # Built from the configured BASE_URL, never from `request.base_url`.
        # The Host header is caller-controlled, and this value is persisted and
        # later handed to every member who opens the resource, so deriving it from
        # the request would store an attacker-chosen URL permanently.
        resource.file_url = f"{settings.BASE_URL.rstrip('/')}/api/choir/{resource.id}/file"
        put_private_file(
            filepath,
            resource.storage_key,
            file.content_type or mimetypes.guess_type(file.filename or "")[0],
            local_root=PRIVATE_UPLOAD_DIR,
        )
        db.commit()
        committed = True
        db.refresh(resource)
    except Exception:
        db.rollback()
        filepath.unlink(missing_ok=True)
        if resource.storage_key and not committed:
            try:
                remove_resource_file(resource)
            except Exception:
                logger.exception("Failed to clean up a resource file after upload failure.")
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

    try:
        remove_resource_file(resource)
        db.delete(resource)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "message": "Resource deleted successfully."
    }
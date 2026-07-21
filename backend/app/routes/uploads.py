from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.choir_resource import ChoirResource
from app.models.user import User
from app.routes.auth_dependency import require_admin

router = APIRouter(
    prefix="/api/uploads",
    tags=["Uploads"],
)

# ==============================
# CONFIGURATION
# ==============================

UPLOAD_DIR = Path("media")

IMAGE_DIR = UPLOAD_DIR / "images"
PDF_DIR = UPLOAD_DIR / "pdfs"
AUDIO_DIR = UPLOAD_DIR / "audio"
VIDEO_DIR = UPLOAD_DIR / "videos"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE = 5 * 1024 * 1024
MAX_PDF = 25 * 1024 * 1024
MAX_AUDIO = 100 * 1024 * 1024
MAX_VIDEO = 500 * 1024 * 1024


def get_destination(filename: str):
    ext = filename.split(".")[-1].lower()

    if ext in ["jpg", "jpeg", "png", "gif", "webp"]:
        return IMAGE_DIR, MAX_IMAGE

    if ext == "pdf":
        return PDF_DIR, MAX_PDF

    if ext in ["mp3", "wav", "m4a", "aac", "ogg"]:
        return AUDIO_DIR, MAX_AUDIO

    if ext in ["mp4", "mov", "avi", "mkv", "webm"]:
        return VIDEO_DIR, MAX_VIDEO

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type.",
    )


# ==============================
# UPLOAD RESOURCE
# ==============================

@router.post("/")
async def upload_resource(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(None),
    language: str = Form("English"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    folder, max_size = get_destination(file.filename)

    contents = await file.read()

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File exceeds maximum allowed size.",
        )

    extension = file.filename.split(".")[-1].lower()

    filename = f"{uuid4().hex}.{extension}"

    filepath = folder / filename

    with open(filepath, "wb") as f:
        f.write(contents)

    resource = ChoirResource(
        title=title,
        description=description,
        category=category,
        language=language,
        filename=filename,
        file_path=str(filepath),
        file_type=extension,
        file_size=len(contents),
        uploaded_by=current_user.id,
        approved=True,
    )

    db.add(resource)
    db.commit()
    db.refresh(resource)

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
    current_user: User = Depends(require_admin),
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

    file = Path(resource.file_path)

    if file.exists():
        file.unlink()

    db.delete(resource)
    db.commit()

    return {
        "message": "Resource deleted successfully."
    }
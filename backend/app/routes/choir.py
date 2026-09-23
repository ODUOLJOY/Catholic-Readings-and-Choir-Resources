from typing import List
import os
import shutil
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.choir import ChoirResource
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)

router = APIRouter(
    prefix="/api/choir",
    tags=["Choir Resources"],
)

UPLOAD_DIR = "uploads/choir"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/")
def get_resources(
    category: str | None = None,
    language: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ChoirResource).filter(
        ChoirResource.is_approved == True,
        ChoirResource.is_published == True,
    )

    if category:
        query = query.filter(ChoirResource.category == category)

    if language:
        query = query.filter(ChoirResource.language == language)

    return query.order_by(
        ChoirResource.created_at.desc()
    ).all()


@router.get("/{resource_id}")
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
):
    resource = (
        db.query(ChoirResource)
        .filter(ChoirResource.id == resource_id)
        .first()
    )

    if not resource:
        raise HTTPException(
            status_code=404,
            detail="Resource not found."
        )

    return resource


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_resource(
    title: str = Form(...),
    category: str = Form(...),
    language: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    extension = file.filename.split(".")[-1].lower()

    allowed = [
        "pdf",
        "mp3",
        "wav",
        "ogg",
        "mp4",
        "jpg",
        "jpeg",
        "png",
    ]

    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type."
        )

    filename = f"{uuid4()}.{extension}"

    filepath = os.path.join(
        UPLOAD_DIR,
        filename,
    )

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    resource = ChoirResource(
        title=title,
        description=description,
        category=category,
        language=language,
        file_url=f"/uploads/choir/{filename}",
        file_type=extension,
        uploaded_by=current_user.id,
        is_approved=False,
        is_published=False,
    )

    db.add(resource)
    db.commit()
    db.refresh(resource)

    return {
        "message": "Choir resource uploaded successfully.",
        "resource": resource,
    }


@router.put("/{resource_id}")
def update_resource(
    resource_id: int,
    title: str = Form(...),
    category: str = Form(...),
    language: str = Form(...),
    description: str = Form(""),
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
            detail="Resource not found."
        )

    resource.title = title
    resource.category = category
    resource.language = language
    resource.description = description

    db.commit()
    db.refresh(resource)

    return resource


@router.delete("/{resource_id}")
def delete_resource(
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
            detail="Resource not found."
        )

    file_path = resource.file_url.split("/media/", 1)[-1]
    file_path = os.path.join("media", file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(resource)
    db.commit()

    return {
        "message": "Resource deleted successfully."
    }


@router.post("/{resource_id}/approve")
def approve_resource(
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
            detail="Resource not found."
        )

    resource.is_approved = True
    resource.is_published = True

    db.commit()

    return {
        "message": "Resource approved."
    }


@router.post("/{resource_id}/reject")
def reject_resource(
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
            detail="Resource not found."
        )

    db.delete(resource)
    db.commit()

    return {
        "message": "Resource rejected."
    }
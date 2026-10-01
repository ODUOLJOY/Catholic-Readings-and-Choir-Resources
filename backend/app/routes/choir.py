from pathlib import Path
import mimetypes
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
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.models.choir import ChoirResource
from app.models.community import ParishMembership
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)
from app.services.authorization import (
    can_manage_choir_resource_scope,
    can_view_choir_resource,
    manageable_choir_parish_ids,
)
from app.services.choir_resources import local_resource_file

router = APIRouter(
    prefix="/api/choir",
    tags=["Choir Resources"],
)

optional_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_optional_user(
    token: str | None,
    db: Session,
) -> User | None:
    if token is None:
        return None
    payload = decode_access_token(token)
    if (
        payload is None
        or payload.get("type") != "access"
        or payload.get("sub") is None
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or disabled.")
    return user


@router.get("/")
def get_resources(
    category: str | None = None,
    language: str | None = None,
    query: str | None = None,
    db: Session = Depends(get_db),
    token: str | None = Depends(optional_bearer),
):
    current_user = get_optional_user(token if isinstance(token, str) else None, db)
    query_obj = db.query(ChoirResource).filter(
        ChoirResource.is_approved == True,
        ChoirResource.is_published == True,
    )
    visible_parishes = (
        set(
            parish_id
            for (parish_id,) in db.query(ParishMembership.parish_id).filter(
                ParishMembership.user_id == current_user.id,
                ParishMembership.status == "active",
            ).all()
        )
        if current_user is not None
        else set()
    )
    if current_user is not None:
        visible_parishes.update(manageable_choir_parish_ids(db, current_user))
    if visible_parishes:
        query_obj = query_obj.filter(
            (ChoirResource.parish_id.is_(None))
            | ChoirResource.parish_id.in_(visible_parishes)
        )
    else:
        query_obj = query_obj.filter(ChoirResource.parish_id.is_(None))

    if category:
        query_obj = query_obj.filter(ChoirResource.category == category)

    if language:
        query_obj = query_obj.filter(ChoirResource.language == language)
        
    if query:
        query_obj = query_obj.filter(
            ChoirResource.title.ilike(f"%{query}%") |
            ChoirResource.description.ilike(f"%{query}%")
        )

    return query_obj.order_by(
        ChoirResource.created_at.desc()
    ).all()


@router.get("/{resource_id}")
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    token: str | None = Depends(optional_bearer),
):
    current_user = get_optional_user(token if isinstance(token, str) else None, db)
    resource = (
        db.query(ChoirResource)
        .filter(
            ChoirResource.id == resource_id,
            ChoirResource.is_approved.is_(True),
            ChoirResource.is_published.is_(True),
        )
        .first()
    )

    if not resource:
        raise HTTPException(
            status_code=404,
            detail="Resource not found."
        )
    if not can_view_choir_resource(db, current_user, resource.parish_id):
        raise HTTPException(status_code=404, detail="Resource not found.")

    return resource


@router.get("/{resource_id}/file")
def get_resource_file(
    resource_id: int,
    db: Session = Depends(get_db),
    token: str | None = Depends(optional_bearer),
):
    current_user = get_optional_user(token if isinstance(token, str) else None, db)
    resource = (
        db.query(ChoirResource)
        .filter(
            ChoirResource.id == resource_id,
            ChoirResource.is_approved.is_(True),
            ChoirResource.is_published.is_(True),
        )
        .first()
    )
    if not resource or not can_view_choir_resource(db, current_user, resource.parish_id):
        raise HTTPException(status_code=404, detail="Resource not found.")
    filepath = local_resource_file(resource)
    if filepath is None or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Resource file not found.")
    return FileResponse(
        filepath,
        media_type=mimetypes.guess_type(filepath.name)[0] or "application/octet-stream",
        filename=filepath.name,
    )


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
    extension = Path(file.filename or "").suffix.lower().lstrip(".")

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

    contents = await file.read(500 * 1024 * 1024 + 1)
    if len(contents) > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed size.")
    private_upload_dir = Path(settings.STORAGE_PATH) / "private_media"
    staging_dir = private_upload_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / f"{uuid4().hex}.{extension}"
    staging_file.write_bytes(contents)

    resource = ChoirResource(
        title=title,
        description=description,
        category=category,
        language=language,
        file_url="/api/choir/pending/file",
        file_type=extension,
        file_size=len(contents),
        uploaded_by=current_user.id,
        is_approved=False,
        is_published=False,
    )

    destination: Path | None = None
    try:
        db.add(resource)
        db.flush()
        destination = (
            private_upload_dir / "resources" / f"{resource.id}.{extension}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        resource.file_url = f"/api/choir/{resource.id}/file"
        staging_file.replace(destination)
        db.commit()
        db.refresh(resource)
    except Exception:
        db.rollback()
        staging_file.unlink(missing_ok=True)
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise

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
            detail="Resource not found."
        )
    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(status_code=403, detail="You cannot manage this resource.")

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
            detail="Resource not found."
        )

    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(status_code=403, detail="You cannot manage this resource.")

    file_path = local_resource_file(resource)
    db.delete(resource)
    db.commit()
    if file_path and file_path.exists():
        file_path.unlink()

    return {
        "message": "Resource deleted successfully."
    }


@router.post("/{resource_id}/approve")
def approve_resource(
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
            detail="Resource not found."
        )
    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(status_code=403, detail="You cannot manage this resource.")

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
            detail="Resource not found."
        )
    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(status_code=403, detail="You cannot manage this resource.")

    file_path = local_resource_file(resource)
    db.delete(resource)
    db.commit()
    if file_path and file_path.exists():
        file_path.unlink()

    return {
        "message": "Resource rejected."
    }
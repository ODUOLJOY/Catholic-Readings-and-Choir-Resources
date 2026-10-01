import mimetypes
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.database import get_db
from app.models.user import User
from app.models.choir import ChoirResource
from app.models.community import CommunityAuditLog, ParishMembership
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)
from app.services.authorization import (
    can_manage_choir_resource_scope,
    can_view_choir_resource,
    manageable_choir_parish_ids,
)
from app.services.private_storage import (
    open_resource_file,
    remove_resource_file,
)
from app.routes.uploads import upload_resource as submit_private_resource

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
    try:
        file_stream = open_resource_file(resource)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Resource file not found.")
    extension = resource.file_type.lower()
    if not extension.isalnum():
        extension = "bin"
    filename = f"resource-{resource.id}.{extension}"
    return StreamingResponse(
        _file_chunks(file_stream),
        media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _file_chunks(file_stream):
    try:
        while chunk := file_stream.read(1024 * 1024):
            yield chunk
    finally:
        file_stream.close()


def _audit_resource_review(
    db: Session,
    user: User,
    resource: ChoirResource,
    action: str,
    reason: str | None = None,
) -> None:
    db.add(
        CommunityAuditLog(
            actor_id=user.id,
            action=action,
            target_type="choir_resource",
            target_id=resource.id,
            scope_type="parish" if resource.parish_id is not None else "global",
            scope_id=resource.parish_id,
            reason=reason,
        )
    )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_resource(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    language: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await submit_private_resource(
        request=request,
        title=title,
        category=category,
        description=description,
        language=language,
        parish_id=None,
        global_scope=True,
        file=file,
        db=db,
        current_user=current_user,
    )


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
    resource.is_approved = False
    resource.is_published = False
    resource.moderation_status = "pending"
    resource.reviewed_by = None
    resource.reviewed_at = None
    resource.rejection_reason = None
    resource.approved_at = None
    resource.published_at = None

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

    remove_resource_file(resource)
    db.delete(resource)
    db.commit()

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
    resource.moderation_status = "approved"
    resource.reviewed_by = current_user.id
    resource.reviewed_at = datetime.now(timezone.utc)
    resource.rejection_reason = None
    resource.approved_at = resource.reviewed_at
    resource.published_at = resource.reviewed_at
    _audit_resource_review(db, current_user, resource, "resource.approved")

    db.commit()

    return {
        "message": "Resource approved."
    }


@router.post("/{resource_id}/reject")
def reject_resource(
    resource_id: int,
    reason: str = Form("Rejected by an authorized reviewer."),
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

    resource.is_approved = False
    resource.is_published = False
    resource.moderation_status = "rejected"
    resource.reviewed_by = current_user.id
    resource.reviewed_at = datetime.now(timezone.utc)
    resource.rejection_reason = reason.strip() or "Rejected by an authorized reviewer."
    resource.approved_at = None
    resource.published_at = None
    _audit_resource_review(
        db,
        current_user,
        resource,
        "resource.rejected",
        resource.rejection_reason,
    )
    db.commit()

    return {
        "message": "Resource rejected."
    }
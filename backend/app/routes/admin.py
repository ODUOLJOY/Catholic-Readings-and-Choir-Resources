from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
import shutil

from app.db.database import get_db
from app.models.readings import Reading
from app.models.choir import ChoirResource
from app.models.user import User
from app.models.parish_request import ParishRequest
from app.models.locations import Diocese, Deanery
from app.models.parish import Parish
from app.models.community import CommunityAuditLog, RoleAssignment
from app.auth.security import decode_token
from app.core.dependencies import get_current_user
from app.routes.auth_dependency import require_super_admin
from app.schemas.user import UserAdminResponse
from app.services.authorization import (
    can_manage_choir_resource_scope,
    manageable_choir_parish_ids,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def require_admin(user: User):
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    # Count admins (both admin and super_admin roles)
    admins_count = db.query(User).filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    return {
        "users": db.query(User).count(),
        "admins": admins_count,
        "readings": db.query(Reading).filter(
            Reading.published == True
        ).count(),
        "choir_resources": db.query(ChoirResource).filter(
            ChoirResource.is_approved == True,
            ChoirResource.is_published == True,
        ).count(),
        "pending_uploads": db.query(Reading).filter(
            Reading.approved == False
        ).count(),
        "pending_reports": 0,  # TODO: implement when Report model is created
        "parish_requests": db.query(ParishRequest).filter(ParishRequest.status == "pending").count(),
    }


@router.get("/users", response_model=list[UserAdminResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(User).order_by(User.created_at.desc()).all()


@router.put("/users/{user_id}/role")
def change_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)

    if role != "user":
        raise HTTPException(
            400,
            "Elevated roles must be granted through an approved scoped role request or the secure bootstrap process.",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.role = role
    user_assignments = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user.id,
        RoleAssignment.is_active.is_(True),
    ).all()
    for assignment in user_assignments:
        assignment.is_active = False
        assignment.revoked_by = current_user.id
        assignment.revoked_at = datetime.now(timezone.utc)
    db.add(
        CommunityAuditLog(
            actor_id=current_user.id,
            action="user.demoted",
            target_type="user",
            target_id=user.id,
            role="user",
            scope_type="global",
            reason="Platform administrator demoted user.",
        )
    )

    db.commit()
    db.refresh(user)

    return {
        "message": "Role updated successfully.",
        "role": role,
    }


@router.put("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.is_active = False
    db.add(
        CommunityAuditLog(
            actor_id=current_user.id,
            action="user.suspended",
            target_type="user",
            target_id=user.id,
            scope_type="global",
        )
    )

    db.commit()

@router.get("/parish-requests")
def get_parish_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    return db.query(ParishRequest).order_by(ParishRequest.created_at.desc()).all()

@router.put("/parish-requests/{request_id}/status")
def update_parish_request(
    request_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    
    req = db.query(ParishRequest).filter(ParishRequest.id == request_id).first()
    if not req:
        raise HTTPException(404, "Request not found.")
        
    req.status = status
    _audit_admin_action(
        db, current_user, f"parish_request.{status}", "parish_request", req.id
    )
    db.commit()
    return {"message": "Status updated."}


@router.put("/users/{user_id}/enable")
def enable_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.is_active = True
    db.add(
        CommunityAuditLog(
            actor_id=current_user.id,
            action="user.reactivated",
            target_type="user",
            target_id=user.id,
            scope_type="global",
        )
    )

    db.commit()

    return {
        "message": "User enabled successfully."
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    db.delete(user)
    _audit_admin_action(db, current_user, "user.deleted", "user", user.id)
    db.commit()

    return {
        "message": "User deleted successfully."
    }


@router.get("/pending")
def pending_readings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return (
        db.query(Reading)
        .filter(Reading.approved == False)
        .order_by(Reading.created_at.desc())
        .all()
    )


@router.get("/pending-resources")
def pending_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pending = db.query(ChoirResource).filter(
        ChoirResource.moderation_status == "pending",
        ChoirResource.is_approved.is_(False),
    )
    if current_user.role == "super_admin":
        pass
    elif current_user.role == "admin":
        parish_ids = manageable_choir_parish_ids(db, current_user)
        if parish_ids:
            pending = pending.filter(
                (ChoirResource.parish_id.is_(None))
                | ChoirResource.parish_id.in_(parish_ids)
            )
        else:
            pending = pending.filter(ChoirResource.parish_id.is_(None))
    else:
        parish_ids = manageable_choir_parish_ids(db, current_user)
        if not parish_ids:
            return []
        pending = pending.filter(ChoirResource.parish_id.in_(parish_ids))
    return pending.order_by(ChoirResource.created_at.desc()).all()


@router.put("/approve-resource/{resource_id}")
def approve_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = db.query(ChoirResource).filter(ChoirResource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found.")
    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(403, "You cannot manage this resource.")
    resource.is_approved = True
    resource.is_published = True
    resource.moderation_status = "approved"
    resource.reviewed_by = current_user.id
    resource.reviewed_at = datetime.now(timezone.utc)
    resource.rejection_reason = None
    resource.approved_at = resource.reviewed_at
    resource.published_at = resource.approved_at
    _audit_admin_action(
        db,
        current_user,
        "resource.approved",
        "choir_resource",
        resource.id,
        "parish" if resource.parish_id is not None else "global",
        resource.parish_id,
    )
    db.commit()
    return {"message": "Resource approved successfully."}


@router.delete("/resources/{resource_id}")
def reject_resource(
    resource_id: int,
    reason: str = Query("Rejected by an authorized reviewer.", max_length=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = db.query(ChoirResource).filter(ChoirResource.id == resource_id).first()
    if not resource:
        raise HTTPException(404, "Resource not found.")
    if not can_manage_choir_resource_scope(db, current_user, resource.parish_id):
        raise HTTPException(403, "You cannot manage this resource.")
    resource.is_approved = False
    resource.is_published = False
    resource.moderation_status = "rejected"
    resource.reviewed_by = current_user.id
    resource.reviewed_at = datetime.now(timezone.utc)
    resource.rejection_reason = (
        reason.strip() or "Rejected by an authorized reviewer."
    )
    _audit_admin_action(
        db,
        current_user,
        "resource.rejected",
        "choir_resource",
        resource_id,
        "parish" if resource.parish_id is not None else "global",
        resource.parish_id,
        resource.rejection_reason,
    )
    db.commit()
    return {"message": "Resource rejected successfully."}


@router.put("/approve/{reading_id}")
def approve_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(404, "Reading not found.")

    reading.approved = True
    reading.published = True
    _audit_admin_action(db, current_user, "reading.published", "reading", reading.id)

    db.commit()
    db.refresh(reading)

    return {
        "message": "Reading approved successfully."
    }


@router.delete("/readings/{reading_id}")
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    reading = db.query(Reading).filter(
        Reading.id == reading_id
    ).first()

    if not reading:
        raise HTTPException(404, "Reading not found.")

    db.delete(reading)
    _audit_admin_action(db, current_user, "reading.deleted", "reading", reading.id)
    db.commit()

    return {
        "message": "Reading deleted successfully."
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    extension = Path(file.filename).suffix.lower()

    allowed = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".mp3",
        ".wav",
        ".mp4",
        ".mov",
    ]

    if extension not in allowed:
        raise HTTPException(
            400,
            "Unsupported file type.",
        )

    filename = f"{uuid4()}{extension}"

    destination = UPLOAD_DIR / filename

    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Upload successful.",
        "filename": filename,
        "url": f"/uploads/{filename}",
    }


def _audit_admin_action(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: int,
    scope_type: str = "global",
    scope_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        CommunityAuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            role=actor.role,
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
        )
    )
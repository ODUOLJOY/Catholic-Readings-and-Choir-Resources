"""Enhanced admin routes with permission-based access control."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole, UserStatus
from app.models.community import CommunityAuditLog
from app.models.choir import ChoirResource
from app.models.readings import Reading
from app.services.authorization_enhanced import (
    can_manage_user,
    can_assign_role,
    check_last_super_admin,
    can_suspend_self,
    get_scoped_user_query,
    normalize_role_value,
)

router = APIRouter(
    prefix="/api/v2/admin",
    tags=["Admin v2"],
)


def _audit_action(
    db: Session,
    actor,
    action: str,
    target_type: str,
    target_id: int,
    scope_type: str = "global",
    scope_id: Optional[int] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    reason: Optional[str] = None,
):
    """Record an administrative action in the audit log."""
    db.add(
        CommunityAuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            role=normalize_role_value(actor.role),
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
        )
    )


@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Admin dashboard with scoped statistics."""
    # Require admin-level access
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    
    # Get scoped user query
    user_query = get_scoped_user_query(db, current_user)
    
    stats = {
        "users": {
            "total": user_query.count(),
            "active": user_query.filter(User.is_active == True).count(),
        },
        "content": {
            "readings": db.query(Reading).filter(Reading.published == True).count(),
            "choir_resources": db.query(ChoirResource).filter(
                ChoirResource.is_approved == True,
                ChoirResource.is_published == True
            ).count(),
            "pending_resources": db.query(ChoirResource).filter(
                ChoirResource.moderation_status == "pending"
            ).count(),
        },
    }
    
    return stats


@router.get("/users")
def list_users(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List users with pagination and filtering (scoped to actor's permissions)."""
    # Require admin-level access
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    
    query = get_scoped_user_query(db, current_user)
    
    # Apply filters
    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    
    if status:
        try:
            user_status = UserStatus(status)
            query = query.filter(User.status == user_status)
        except ValueError:
            pass  # Invalid status, ignore
    
    if role:
        try:
            user_role = UserRole(role)
            query = query.filter(User.role == user_role)
        except ValueError:
            pass  # Invalid role, ignore
    
    # Pagination
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.put("/users/{user_id}/suspend")
def suspend_user(
    user_id: int,
    reason: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Suspend a user account."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if not can_manage_user(db, current_user, target_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user."
        )
    
    # Self-protection
    if target_user.id == current_user.id and not can_suspend_self(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot suspend yourself if you are the last super admin."
        )
    
    target_user.status = UserStatus.SUSPENDED
    target_user.is_active = False
    target_user.suspended_at = datetime.now(timezone.utc)
    target_user.suspended_by = current_user.id
    target_user.suspension_reason = reason
    
    _audit_action(
        db, current_user, "user.suspended", "user", user_id,
        scope_type="global", reason=reason
    )
    
    db.commit()
    
    return {"message": "User suspended successfully."}


@router.put("/users/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Reactivate a suspended user."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if not can_manage_user(db, current_user, target_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user."
        )
    
    target_user.status = UserStatus.ACTIVE
    target_user.is_active = True
    target_user.suspended_at = None
    target_user.suspended_by = None
    target_user.suspension_reason = None
    
    _audit_action(db, current_user, "user.reactivated", "user", user_id)
    
    db.commit()
    
    return {"message": "User reactivated successfully."}


@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    new_role: str,
    reason: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Change a user's role (with proper authorization and audit trail)."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    try:
        role_enum = UserRole(new_role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role.")
    
    if not can_assign_role(db, current_user, target_user, role_enum):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to assign this role to this user."
        )
    
    old_role = target_user.role
    target_user.role = role_enum.value
    
    _audit_action(
        db, current_user, "role.changed", "user", user_id,
        old_value=old_role, new_value=new_role, reason=reason
    )
    
    db.commit()
    
    return {"message": "Role changed successfully.", "old_role": old_role, "new_role": new_role}


@router.get("/moderation/queue")
def moderation_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """View moderation queue (pending choir resources)."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required."
        )
    
    query = db.query(ChoirResource).filter(
        ChoirResource.moderation_status == "pending"
    )
    
    if status:
        query = query.filter(ChoirResource.moderation_status == status)
    
    total = query.count()
    resources = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "resources": resources,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """View audit logs (scoped to actor's permissions)."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    
    query = db.query(CommunityAuditLog)
    
    if action:
        query = query.filter(CommunityAuditLog.action == action)
    
    # Moderators only see moderation-related logs
    if current_user.role == UserRole.MODERATOR:
        moderation_actions = [
            "resource.approved",
            "resource.rejected",
            "moderation.action",
        ]
        query = query.filter(CommunityAuditLog.action.in_(moderation_actions))
    
    query = query.order_by(CommunityAuditLog.id.desc())
    
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }

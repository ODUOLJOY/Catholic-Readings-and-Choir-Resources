"""Enhanced authorization service with explicit permissions and self-protection."""
from typing import Optional

from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.community import RoleAssignment
from app.models.permissions import Permission, RolePermission, DEFAULT_ROLE_PERMISSIONS
from app.models.user import User, UserRole, UserStatus
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.community import CommunityGroup, GroupMembership, ParishMembership


class AuthorizationError(Exception):
    """Authorization error with context."""
    def __init__(self, message: str, code: str = "FORBIDDEN"):
        self.message = message
        self.code = code
        super().__init__(message)


def normalize_role_value(role) -> str:
    """Return the stored string value for a role.

    ``User.role`` is a plain ``String`` column, so SQLAlchemy hands back a plain
    ``str`` once the instance has been refreshed from the database, while a
    freshly assigned instance still holds the ``UserRole`` enum member. Reading
    ``.value`` blindly therefore raises ``AttributeError`` for any user loaded
    from a session.
    """
    return role.value if isinstance(role, UserRole) else str(role)


def actor_diocese_id(db: Session, actor: User) -> Optional[int]:
    """Return the diocese an administrative actor is scoped to.

    A diocesan administrator is attached to the organisation through a parish,
    so their diocese is derived from that parish. ``None`` is returned whenever
    the scope cannot be established -- an unscoped actor must never be treated
    as having access to everything.
    """
    if actor is None or actor.parish_id is None:
        return None
    parish = db.query(Parish).filter(Parish.id == actor.parish_id).first()
    if parish is None:
        return None
    return parish.diocese_id


def has_permission(db: Session, user: User, permission: str) -> bool:
    """Check if user has a specific permission.

    The ``role_permissions`` table is the sole authority and a role with no rows
    holds no permissions. This is deliberately fail-closed: the granular
    permission system exists so that holding a scope (a diocese, a parish) never
    implies the right to act inside it, and a permissive fallback would quietly
    undo that. Where a role genuinely needs its default powers, grant the rows
    explicitly -- see ``app.services.permission_seed``.
    """
    if user.role == UserRole.SUPER_ADMIN:
        return True

    # Check if user's role has the permission
    role_perms = db.query(RolePermission).join(Permission).filter(
        RolePermission.role == normalize_role_value(user.role),
        Permission.name == permission
    ).first()

    return role_perms is not None


def has_any_permission(db: Session, user: User, permissions: list[str]) -> bool:
    """Check if user has any of the specified permissions."""
    if user.role == UserRole.SUPER_ADMIN:
        return True

    role_perms = db.query(RolePermission).join(Permission).filter(
        RolePermission.role == normalize_role_value(user.role),
        Permission.name.in_(permissions)
    ).first()

    return role_perms is not None


def has_all_permissions(db: Session, user: User, permissions: list[str]) -> bool:
    """Check if user has all of the specified permissions."""
    if user.role == UserRole.SUPER_ADMIN:
        return True

    count = db.query(RolePermission).join(Permission).filter(
        RolePermission.role == normalize_role_value(user.role),
        Permission.name.in_(permissions)
    ).distinct().count()

    return count == len(permissions)


def can_manage_user(db: Session, actor: User, target_user: User) -> bool:
    """Check if actor can manage target_user."""
    # Super admin can manage anyone
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    
    # Cannot manage super admin
    if target_user.role == UserRole.SUPER_ADMIN:
        return False
    
    # Cannot manage someone with higher role
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.CHOIR_CONTRIBUTOR: 1,
        UserRole.PARISH_ADMINISTRATOR: 2,
        UserRole.DIOCESAN_ADMINISTRATOR: 3,
        UserRole.MODERATOR: 4,
        UserRole.ADMIN: 5,
        UserRole.SUPER_ADMIN: 6,
    }
    
    if role_hierarchy.get(actor.role, 0) < role_hierarchy.get(target_user.role, 0):
        return False
    
    # Scope-based checks
    if actor.role in [UserRole.PARISH_ADMINISTRATOR, UserRole.DIOCESAN_ADMINISTRATOR]:
        # Check if they share organizational scope
        if actor.parish_id and target_user.parish_id:
            if actor.parish_id == target_user.parish_id:
                return True
        if actor.role == UserRole.DIOCESAN_ADMINISTRATOR:
            # Diocesan admin can manage users in their diocese
            actor_diocese = actor_diocese_id(db, actor)
            target_parish = db.query(Parish).filter(Parish.id == target_user.parish_id).first()
            if (
                actor_diocese is not None
                and target_parish is not None
                and actor_diocese == target_parish.diocese_id
            ):
                return True
    
    # Admin and moderator can manage users (within scope)
    if actor.role in [UserRole.ADMIN, UserRole.MODERATOR]:
        return has_permission(db, actor, "users.update")
    
    return False


def can_assign_role(db: Session, actor: User, target_user: User, new_role: UserRole) -> bool:
    """Check if actor can assign new_role to target_user."""
    # Super admin can assign any role
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    
    # Self-protection: cannot modify own role to something higher
    if actor.id == target_user.id:
        role_hierarchy = {
            UserRole.USER: 0,
            UserRole.CHOIR_CONTRIBUTOR: 1,
            UserRole.PARISH_ADMINISTRATOR: 2,
            UserRole.DIOCESAN_ADMINISTRATOR: 3,
            UserRole.MODERATOR: 4,
            UserRole.ADMIN: 5,
            UserRole.SUPER_ADMIN: 6,
        }
        if role_hierarchy.get(new_role, 0) > role_hierarchy.get(actor.role, 0):
            return False
    
    # Cannot assign super admin
    if new_role == UserRole.SUPER_ADMIN:
        return False
    
    # Cannot assign diocesan admin
    if new_role == UserRole.DIOCESAN_ADMINISTRATOR:
        return False
    
    # Check actor's role hierarchy
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.CHOIR_CONTRIBUTOR: 1,
        UserRole.PARISH_ADMINISTRATOR: 2,
        UserRole.DIOCESAN_ADMINISTRATOR: 3,
        UserRole.MODERATOR: 4,
        UserRole.ADMIN: 5,
        UserRole.SUPER_ADMIN: 6,
    }
    
    if role_hierarchy.get(actor.role, 0) < role_hierarchy.get(new_role, 0):
        return False
    
    # Role-specific rules
    if actor.role == UserRole.ADMIN:
        # Admin can assign user, choir_contributor, moderator
        return new_role in [UserRole.USER, UserRole.CHOIR_CONTRIBUTOR, UserRole.MODERATOR]
    
    if actor.role == UserRole.DIOCESAN_ADMINISTRATOR:
        # Diocesan admin can assign parish_admin within their diocese
        if new_role == UserRole.PARISH_ADMINISTRATOR:
            # Check scope
            if actor.parish_id and target_user.parish_id:
                actor_parish = db.query(Parish).filter(Parish.id == actor.parish_id).first()
                target_parish = db.query(Parish).filter(Parish.id == target_user.parish_id).first()
                if actor_parish and target_parish and actor_parish.diocese_id == target_parish.diocese_id:
                    return True
        return new_role in [UserRole.USER, UserRole.CHOIR_CONTRIBUTOR]
    
    if actor.role == UserRole.PARISH_ADMINISTRATOR:
        # Parish admin can only assign user and choir_contributor
        return new_role in [UserRole.USER, UserRole.CHOIR_CONTRIBUTOR]
    
    return False


def check_last_super_admin(db: Session) -> bool:
    """Check if there's only one super admin remaining."""
    count = db.query(User).filter(
        User.role == UserRole.SUPER_ADMIN,
        User.is_active == True
    ).count()
    return count == 1


def can_suspend_self(db: Session, user: User) -> bool:
    """Prevent super admin from suspending themselves if they're the last one."""
    if user.role != UserRole.SUPER_ADMIN:
        return True
    return not check_last_super_admin(db)


def can_modify_parish(db: Session, actor: User, parish_id: int) -> bool:
    """Check if actor can modify a parish."""
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    
    parish = db.query(Parish).filter(Parish.id == parish_id).first()
    if not parish:
        return False
    
    # Parish admin can only modify their own parish
    if actor.role == UserRole.PARISH_ADMINISTRATOR:
        return actor.parish_id == parish_id
    
    # Diocesan admin can modify parishes in their diocese, and only when the
    # granular permission has actually been granted to the role.
    if actor.role == UserRole.DIOCESAN_ADMINISTRATOR:
        actor_diocese = actor_diocese_id(db, actor)
        if actor_diocese is None or actor_diocese != parish.diocese_id:
            return False
        return has_permission(db, actor, "parishes.update")
    
    # Admin can modify any parish
    if actor.role == UserRole.ADMIN:
        return has_permission(db, actor, "parishes.update")
    
    return False


def can_modify_diocese(db: Session, actor: User, diocese_id: int) -> bool:
    """Check if actor can modify a diocese.

    A diocesan administrator is scoped to the diocese they are attached to and
    additionally needs the ``dioceses.update`` permission, which matches the
    ``"dioceses.update",  # Only own diocese`` entry in
    ``DEFAULT_ROLE_PERMISSIONS``. A sibling diocese is refused, and so is an
    actor whose scope cannot be established at all.
    """
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    
    # Only super admin and admin can modify dioceses
    if actor.role == UserRole.ADMIN:
        return has_permission(db, actor, "dioceses.update")

    if actor.role == UserRole.DIOCESAN_ADMINISTRATOR:
        actor_diocese = actor_diocese_id(db, actor)
        if actor_diocese is None or actor_diocese != diocese_id:
            return False
        return has_permission(db, actor, "dioceses.update")

    return False


def can_grant_permission(db: Session, actor: User, *, role, permission: str) -> bool:
    """Check whether ``actor`` may grant ``permission`` to ``role``.

    Granting permissions is how privileges are escalated, so it is restricted to
    super admins and administrators, and an administrator can never widen their
    own role: that is the self-grant escalation path.
    """
    if actor.role == UserRole.SUPER_ADMIN:
        return True

    if actor.role != UserRole.ADMIN:
        return False

    # Self-grant: an administrator may not extend the permissions of the role
    # they themselves hold.
    if normalize_role_value(role) == normalize_role_value(actor.role):
        return False

    if not has_permission(db, actor, "roles.update"):
        return False

    # An administrator may only hand out permissions they already hold.
    return has_permission(db, actor, permission)


def get_scoped_user_query(db: Session, actor: User):
    """Return a user query scoped to actor's permissions."""
    base_query = db.query(User)
    
    if actor.role == UserRole.SUPER_ADMIN:
        return base_query
    
    if actor.role == UserRole.ADMIN:
        return base_query
    
    if actor.role == UserRole.DIOCESAN_ADMINISTRATOR:
        actor_diocese = actor_diocese_id(db, actor)
        if actor_diocese is None:
            # An unscoped actor must never be treated as having diocesan-wide
            # visibility. Fail closed to their own record.
            return base_query.filter(User.id == actor.id)
        return base_query.join(Parish, User.parish_id == Parish.id).filter(
            Parish.diocese_id == actor_diocese
        )
    
    if actor.role == UserRole.PARISH_ADMINISTRATOR:
        if actor.parish_id:
            return base_query.filter(User.parish_id == actor.parish_id)
        return base_query.filter(User.id == actor.id)  # Only self if no parish
    
    # Regular users can only see themselves
    return base_query.filter(User.id == actor.id)


def can_approve_content(db: Session, actor: User, resource_uploader_id: int) -> bool:
    """Prevent self-approval of content."""
    if actor.id == resource_uploader_id:
        return False
    
    if actor.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MODERATOR]:
        return has_permission(db, actor, "choir_resources.approve")
    
    if actor.role == UserRole.PARISH_ADMINISTRATOR:
        return has_permission(db, actor, "choir_resources.approve")
    
    return False

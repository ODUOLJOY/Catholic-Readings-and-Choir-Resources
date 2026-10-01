"""Provision the configured initial platform administrator for an existing account."""

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.community import CommunityAuditLog, RoleAssignment
from app.models.user import User


def bootstrap() -> None:
    email = settings.BOOTSTRAP_SUPER_ADMIN_EMAIL.strip().lower()
    if not email:
        raise RuntimeError("BOOTSTRAP_SUPER_ADMIN_EMAIL must be configured.")
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).with_for_update().first()
        if user is None:
            raise RuntimeError("The configured bootstrap account must register before provisioning.")
        if not user.is_verified:
            raise RuntimeError("The configured bootstrap account must verify its email first.")
        user.role = "super_admin"
        assignment = db.query(RoleAssignment).filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role == "super_admin",
            RoleAssignment.scope_type == "global",
            RoleAssignment.scope_id.is_(None),
            RoleAssignment.is_active.is_(True),
        ).first()
        if assignment is None:
            db.add(
                RoleAssignment(
                    user_id=user.id,
                    role="super_admin",
                    scope_type="global",
                    scope_id=None,
                    granted_by=user.id,
                )
            )
        db.add(
            CommunityAuditLog(
                actor_id=user.id,
                action="super_admin.bootstrap",
                target_type="user",
                target_id=user.id,
                role="super_admin",
                scope_type="global",
                reason="Authorized bootstrap command.",
            )
        )
        db.commit()


if __name__ == "__main__":
    bootstrap()
    print("Configured super administrator provisioned.")

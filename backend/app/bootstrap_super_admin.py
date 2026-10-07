"""Provision the configured initial platform administrator.

This script is idempotent and safe to run on every application start-up. It
ensures that the account named in ``BOOTSTRAP_SUPER_ADMIN_EMAIL`` exists, is
email-verified, has its password set to ``BOOTSTRAP_SUPER_ADMIN_PASSWORD``, and
holds the global ``super_admin`` role together with a matching
``RoleAssignment``.
"""

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.community import CommunityAuditLog, RoleAssignment
from app.models.user import User
from app.auth.security import hash_password, verify_password
from app.services.auth_service import _generate_unique_username


@contextmanager
def _session_scope(db: Session | None):
    if db is not None:
        yield db
    else:
        with SessionLocal() as session:
            yield session


def _ensure_role_assignment(
    session: Session, user_id: int, granted_by: int
) -> None:
    """Create a global super_admin RoleAssignment if one is not already active."""
    assignment = session.query(RoleAssignment).filter(
        RoleAssignment.user_id == user_id,
        RoleAssignment.role == "super_admin",
        RoleAssignment.scope_type == "global",
        RoleAssignment.scope_id.is_(None),
        RoleAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        session.add(
            RoleAssignment(
                user_id=user_id,
                role="super_admin",
                scope_type="global",
                scope_id=None,
                ministry=None,
                granted_by=granted_by,
            )
        )


def bootstrap(db: Session | None = None) -> None:
    email = settings.BOOTSTRAP_SUPER_ADMIN_EMAIL.strip().lower()
    if not email:
        raise RuntimeError("BOOTSTRAP_SUPER_ADMIN_EMAIL must be configured.")

    password = settings.BOOTSTRAP_SUPER_ADMIN_PASSWORD
    if not password:
        raise RuntimeError(
            "BOOTSTRAP_SUPER_ADMIN_PASSWORD must be configured."
        )

    with _session_scope(db) as session:
        user = (
            session.query(User)
            .filter(User.email == email)
            .with_for_update()
            .first()
        )

        if user is None:
            # The bootstrap account does not exist yet — create it directly
            # rather than delegating to the full registration flow (which
            # would require a verified email round-trip).
            user = User(
                full_name="Super Admin",
                email=email,
                username=_generate_unique_username(session, email),
                hashed_password=hash_password(password),
                role="user",
                is_active=True,
                is_verified=True,
                profile_setup_completed=True,
            )
            session.add(user)
            session.flush()
        else:
            # Always (re)set the password so a rotated BOOTSTRAP_SUPER_ADMIN_PASSWORD
            # takes effect immediately, even if the account already existed.
            user.hashed_password = hash_password(password)
            user.is_verified = True

        user.role = "super_admin"
        _ensure_role_assignment(session, user.id, granted_by=user.id)

        session.add(
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
        session.commit()


if __name__ == "__main__":
    bootstrap()
    print("Configured super administrator provisioned.")

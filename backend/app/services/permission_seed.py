"""Idempotent seeding of the granular permission table.

Why this exists
---------------
The migration ``20261002_09_permissions`` created ``permissions`` and
``role_permissions`` but inserted **no rows**. ``app.models.permissions`` already
declares the intended grants in ``DEFAULT_ROLE_PERMISSIONS``, but nothing ever
copied them into the database, and ``has_permission`` consults only the database.

The result was that every role except ``super_admin`` held zero permissions: a
parish or diocesan administrator could not read users, approve content, or
perform any other administrator action, regardless of their role. Every such
request was refused.

This module also seeds the ``permissions`` table from ``PERMISSIONS`` in the
models, which the ``20261002_09_permissions`` migration likewise left empty.

Why the fallback in the authorization layer was the wrong fix
-------------------------------------------------------------
It is tempting to make ``has_permission`` fall back to ``DEFAULT_ROLE_PERMISSIONS``
when a role has no rows. That inverts the security model. The granular permission
system exists so that holding a *scope* never implies the right to *act* inside it,
and the repository's own tests assert that a role with no rows is refused:

    test_diocesan_admin_without_permission_cannot_modify_own_diocese
    test_parish_admin_approves_only_with_permission

A fallback makes those roles permissive and would silently widen every
unseeded role in the deployment. Seeding the declared grants instead keeps
``has_permission`` fail-closed while restoring the intended behaviour.

Run it with::

    python -m app.services.permission_seed
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSIONS,
    Permission,
    RolePermission,
)

logger = logging.getLogger(__name__)

# Recorded against seeded rows so an operator can tell them apart from grants a
# human administrator made deliberately.
SEED_GRANTED_BY = "system-seed"


def seed_permissions(db: Session) -> dict[str, int]:
    """Create the declared permissions and role grants. Returns a change summary.

    Safe to run repeatedly: existing rows are left untouched, and a role is only
    provisioned if it has no grants at all. Once a role has grants, they are an
    administrator's deliberate state -- including the deliberate *absence* of a
    permission -- and this module will not add anything back.
    """
    permissions_created = 0
    for name, description in PERMISSIONS.items():
        existing = db.execute(
            select(Permission).where(Permission.name == name)
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                Permission(name=name, description=description, category=_category_for(name))
            )
            permissions_created += 1
    db.flush()

    grants_created = 0
    for role, names in DEFAULT_ROLE_PERMISSIONS.items():
        # Only provision a role that has *never* been granted anything. Once a
        # role has rows, its grants are an administrator's deliberate state and
        # must survive re-running this module: otherwise deleting a single grant
        # to narrow a role would silently undo itself on the next deploy.
        already_provisioned = (
            db.execute(
                select(func.count())
                .select_from(RolePermission)
                .where(RolePermission.role == role)
            ).scalar_one()
        )
        if already_provisioned:
            continue

        for name in names:
            permission = db.execute(
                select(Permission).where(Permission.name == name)
            ).scalar_one_or_none()
            if permission is None:
                # A grant referencing an undeclared permission is a data bug, not
                # something to paper over by inventing a permission.
                raise RuntimeError(
                    f"DEFAULT_ROLE_PERMISSIONS grants '{name}' to '{role}', but that "
                    "permission is not declared in PERMISSIONS."
                )
            db.add(
                RolePermission(
                    role=role,
                    permission_id=permission.id,
                    granted_by=SEED_GRANTED_BY,
                )
            )
            grants_created += 1

    db.commit()
    summary = {
        "permissions_created": permissions_created,
        "role_grants_created": grants_created,
    }
    logger.info("Permission seed complete: %s", summary)
    return summary


def _category_for(permission_name: str) -> str:
    """Derive a permission's category from its ``<resource>.<action>`` name."""
    resource = permission_name.split(".", 1)[0]
    return resource.replace("_", " ")


def check_permission_seed(db: Session) -> dict:
    """Verify every declared permission exists and every default role is provisioned.

    Returns a summary dict with ``ok`` plus the problems found.

    Per-role rather than a single total count on purpose. A total of zero is the
    obvious failure, but a partial seed -- the process interrupted between roles,
    or one role's grants deleted by hand -- still leaves the affected role unable
    to do anything while ``count(*) > 0`` reports success.

    A role whose *declared* grants are non-empty but which holds none in the
    database is reported as unprovisioned, which matches :func:`seed_permissions`' own
    rule that zero grants means "never seeded".

    A role declared with an empty grant list is skipped, not reported. ``super_admin``
    is the case in point: it bypasses the permission table entirely in
    :func:`app.services.authorization_enhanced.has_permission`, so it is correctly
    granted nothing and a freshly seeded database must still pass this check.
    Flagging it would make the startup gate refuse to boot a healthy deployment.
    """
    problems: list[str] = []

    try:
        missing_permissions = sorted(
            name
            for name in PERMISSIONS
            if db.execute(
                select(Permission.id).where(Permission.name == name)
            ).scalar_one_or_none()
            is None
        )
    except SQLAlchemyError as error:
        # A database that has never had the permission tables reports this as a
        # ProgrammingError. An operator-facing gate must say so and exit 1, not
        # dump a driver traceback, because the remedy is "run the migrations",
        # which a traceback hides.
        return {
            "ok": False,
            "problems": [
                "the permissions tables are missing or unreadable; apply the "
                f"migrations before seeding ({error.__class__.__name__})"
            ],
            "total_grants": 0,
            "declared_permissions": len(PERMISSIONS),
            "declared_roles": len(DEFAULT_ROLE_PERMISSIONS),
        }
    if missing_permissions:
        problems.append(
            f"{len(missing_permissions)} declared permission(s) are missing: "
            f"{', '.join(missing_permissions[:5])}"
        )

    unprovisioned: list[str] = []
    for role, names in DEFAULT_ROLE_PERMISSIONS.items():
        if not names:
            # Declared as holding nothing on purpose (super_admin bypasses the
            # permission table), so no rows is the correct state, not a gap.
            continue
        granted = db.execute(
            select(func.count())
            .select_from(RolePermission)
            .where(RolePermission.role == role)
        ).scalar_one()
        if granted == 0:
            unprovisioned.append(role)
    if unprovisioned:
        problems.append(
            f"{len(unprovisioned)} role(s) have no permission grants: "
            f"{', '.join(sorted(unprovisioned))}"
        )

    total_grants = db.execute(select(func.count()).select_from(RolePermission)).scalar_one()
    return {
        "ok": not problems,
        "problems": problems,
        "total_grants": total_grants,
        "declared_permissions": len(PERMISSIONS),
        "declared_roles": len(DEFAULT_ROLE_PERMISSIONS),
    }


def main() -> int:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    check_only = "--check" in sys.argv[1:]
    from app.db.database import SessionLocal, engine

    if check_only:
        with Session(engine) as db:
            summary = check_permission_seed(db)

        if summary["ok"]:
            print(
                "permission seed check: "
                f"{summary['total_grants']} grants across "
                f"{summary['declared_roles']} roles, "
                f"{summary['declared_permissions']} permissions declared"
            )
            return 0

        logger.error("Permission seed check failed:")
        for problem in summary["problems"]:
            logger.error("  - %s", problem)
        logger.error(
            "Seed them explicitly: python -m app.services.permission_seed"
        )
        return 1

    with SessionLocal() as db:
        summary = seed_permissions(db)
    print(f"permission seed: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
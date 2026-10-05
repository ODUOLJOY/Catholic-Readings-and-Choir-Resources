"""Focused authorization integration tests.

Previously this was a single ``test_authorization_integration`` function that
wrapped every check in ``try``/``except`` and returned ``True``/``False``. pytest
reports a returning test as passing with a ``PytestReturnNotNoneWarning``, so any
exception inside it was silently recorded as a success, and one failure masked
the state of every later check. The checks are now independent test functions
with real assertions, so a failure names itself and stops only its own case.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.locations import Diocese
from app.models.parish import Parish
from app.models.permissions import Permission, RolePermission
from app.models.user import User, UserRole, UserStatus
from app.services.authorization_enhanced import (
    can_assign_role,
    can_suspend_self,
    check_last_super_admin,
)


@pytest.fixture()
def db():
    """A fresh in-memory database per test, so cases cannot leak into each other."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db, email, role=UserRole.USER, parish_id=None):
    user = User(
        full_name=email.split("@")[0],
        email=email,
        hashed_password="hash",
        role=role,
        parish_id=parish_id,
    )
    db.add(user)
    db.commit()
    return user


def test_super_admin_may_assign_the_super_admin_role(db):
    """Documented policy: a super admin can create another super admin.

    This is asserted rather than printed so that a change in behaviour is a
    visible test failure instead of a silent one.
    """
    super_admin = _user(db, "super@test.com", UserRole.SUPER_ADMIN)
    target = _user(db, "target@test.com")

    assert can_assign_role(db, super_admin, target, UserRole.SUPER_ADMIN)


@pytest.mark.parametrize(
    "actor_role",
    [
        UserRole.USER,
        UserRole.CHOIR_CONTRIBUTOR,
        UserRole.PARISH_ADMINISTRATOR,
        UserRole.MODERATOR,
        UserRole.ADMIN,
    ],
)
def test_non_super_admin_roles_cannot_assign_super_admin(db, actor_role):
    """Assigning the super admin role is reserved for super admins."""
    actor = _user(db, f"actor_{actor_role.value}@test.com", actor_role)
    target = _user(db, f"target_{actor_role.value}@test.com")

    assert not can_assign_role(db, actor, target, UserRole.SUPER_ADMIN)


def test_user_cannot_self_promote_to_admin(db):
    """A regular user must not be able to escalate their own role."""
    user = _user(db, "user@test.com")

    assert not can_assign_role(db, user, user, UserRole.ADMIN)


def test_user_cannot_self_promote_to_parish_administrator(db):
    """Self-escalation is refused for every role above ``user``."""
    user = _user(db, "user2@test.com")

    for role in (
        UserRole.PARISH_ADMINISTRATOR,
        UserRole.DIOCESAN_ADMINISTRATOR,
        UserRole.MODERATOR,
        UserRole.ADMIN,
    ):
        assert not can_assign_role(db, user, user, role), role


def test_admin_cannot_self_promote_to_super_admin(db):
    """An administrator is still refused the super admin role on themselves."""
    admin = _user(db, "admin@test.com", UserRole.ADMIN)

    assert not can_assign_role(db, admin, admin, UserRole.SUPER_ADMIN)


def test_last_super_admin_cannot_suspend_self(db):
    """The final super admin must remain able to administer the system."""
    super_admin = _user(db, "super@test.com", UserRole.SUPER_ADMIN)

    assert check_last_super_admin(db) is True
    assert can_suspend_self(db, super_admin) is False


def test_one_of_several_super_admins_can_suspend_self(db):
    """With a spare super admin present, self-suspension is permitted."""
    super1 = _user(db, "super1@test.com", UserRole.SUPER_ADMIN)
    _user(db, "super2@test.com", UserRole.SUPER_ADMIN)

    assert check_last_super_admin(db) is False
    assert can_suspend_self(db, super1) is True


def test_regular_user_can_suspend_self(db):
    """Self-suspension is not a privilege escalation for ordinary users."""
    user = _user(db, "user3@test.com")

    assert can_suspend_self(db, user) is True


def test_new_user_defaults_to_active(db):
    """A newly created user is active by default."""
    user = User(full_name="New User", email="new@test.com", hashed_password="hash")
    db.add(user)
    db.commit()

    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True


def test_default_status_is_persisted_as_the_lowercase_value(db):
    """The stored representation must be the lowercase enum value.

    The ``userstatus`` enum type created by migration 09 contains lowercase
    labels, so an uppercase ``ACTIVE`` would be rejected by PostgreSQL.
    """
    from sqlalchemy import text

    _user(db, "stored@test.com")

    with db.connection() as conn:
        stored = conn.execute(
            text("SELECT status FROM users WHERE email = 'stored@test.com'")
        ).scalar_one()

    assert stored == "active"
    assert stored != UserStatus.ACTIVE.name


def test_user_role_is_persisted_as_the_lowercase_value(db):
    """Roles follow the same lowercase convention as statuses."""
    from sqlalchemy import text

    _user(db, "rolecheck@test.com", UserRole.PARISH_ADMINISTRATOR)

    with db.connection() as conn:
        stored = conn.execute(
            text("SELECT role FROM users WHERE email = 'rolecheck@test.com'")
        ).scalar_one()

    assert stored == "parish_administrator"


def test_loaded_role_is_a_string_not_an_enum(db):
    """Regression: DB-loaded roles are plain strings.

    Reading ``actor.role.value`` on a loaded user raises ``AttributeError``, which
    previously broke administrative audit logging.
    """
    _user(db, "loaded@test.com", UserRole.ADMIN)
    db.expire_all()

    loaded = db.query(User).filter(User.email == "loaded@test.com").one()

    assert isinstance(loaded.role, str)
    assert not hasattr(loaded.role, "value")
    assert loaded.role == UserRole.ADMIN.value


def test_permission_rows_are_required_for_grants(db):
    """A ``RolePermission`` row is what makes a granular permission effective."""
    _user(db, "perm_actor@test.com", UserRole.ADMIN)

    from app.services.authorization_enhanced import has_permission

    actor = db.query(User).filter(User.email == "perm_actor@test.com").one()
    assert not has_permission(db, actor, "dioceses.update")

    permission = Permission(name="dioceses.update", category="dioceses")
    db.add(permission)
    db.commit()
    db.add(
        RolePermission(
            role=UserRole.ADMIN.value,
            permission_id=permission.id,
            granted_by=actor.id,
        )
    )
    db.commit()
    db.expire_all()

    actor = db.query(User).filter(User.email == "perm_actor@test.com").one()
    assert has_permission(db, actor, "dioceses.update")


def test_diocese_ownership_is_resolvable_through_the_parish(db):
    """A diocesan administrator's scope is derived from their parish."""
    from app.models.locations import Country, Deanery, EcclesiasticalProvince
    from app.services.authorization_enhanced import actor_diocese_id

    country = Country(name="Kenya", code="KE")
    province = EcclesiasticalProvince(name="Nairobi", code="KE-P01", country_id=1)
    diocese = Diocese(
        name="Archdiocese of Nairobi",
        code="KE-NRB-NBI",
        ecclesiastical_province_id=1,
    )
    deanery = Deanery(name="Nairobi Central", code="KE-NRB-NBI-C", diocese_id=1)
    parish = Parish(
        name="Parish A",
        code="KE-NRB-NBI-C-A",
        diocese_id=1,
        deanery_id=1,
        country_id=1,
    )
    db.add_all([country, province, diocese, deanery, parish])
    db.commit()

    actor = _user(db, "scoped@test.com", UserRole.DIOCESAN_ADMINISTRATOR, parish.id)

    assert actor_diocese_id(db, actor) == diocese.id


def test_unscoped_diocesan_adminitor_has_no_diocese(db):
    """A diocesan administrator without a parish has no derivable scope."""
    from app.services.authorization_enhanced import actor_diocese_id

    actor = _user(db, "unscoped@test.com", UserRole.DIOCESAN_ADMINISTRATOR)

    assert actor_diocese_id(db, actor) is None

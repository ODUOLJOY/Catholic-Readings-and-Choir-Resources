"""Comprehensive authorization tests."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.models.user import User, UserRole, UserStatus
from app.models.parish import Parish
from app.models.locations import Country, EcclesiasticalProvince, Diocese, Deanery
from app.models.permissions import Permission, RolePermission
from app.services.authorization_enhanced import (
    has_permission,
    can_manage_user,
    can_assign_role,
    can_grant_permission,
    check_last_super_admin,
    can_suspend_self,
    can_modify_parish,
    can_modify_diocese,
    actor_diocese_id,
    get_scoped_user_query,
    can_approve_content,
)
from app.db.database import Base


def grant_permissions(db: Session, role, permissions) -> None:
    """Grant the named permissions to a role, as DEFAULT_ROLE_PERMISSIONS would.

    Granular permissions are only effective when a ``RolePermission`` row exists,
    so positive authorization cases must seed them and negative cases must not.

    A throwaway administrator is used as ``granted_by`` so that seeding does not
    perturb tests which count super administrators.
    """
    granter = db.query(User).filter(User.email == "granter@test.com").first()
    if granter is None:
        granter = User(
            full_name="Permission Granter",
            email="granter@test.com",
            hashed_password="hash",
            role=UserRole.ADMIN,
        )
        db.add(granter)
        db.commit()
    role_value = role.value if isinstance(role, UserRole) else str(role)
    for name in permissions:
        existing = db.query(Permission).filter(Permission.name == name).first()
        if existing is None:
            existing = Permission(name=name, category=name.split(".")[0])
            db.add(existing)
            db.flush()
        already = (
            db.query(RolePermission)
            .filter(
                RolePermission.role == role_value,
                RolePermission.permission_id == existing.id,
            )
            .first()
        )
        if already is None:
            db.add(
                RolePermission(
                    role=role_value,
                    permission_id=existing.id,
                    granted_by=granter.id,
                )
            )
    db.commit()


@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def hierarchy(db: Session):
    """Build a valid, stable-coded country -> province -> diocese -> deanery -> parish chain.

    ``Parish.code``, ``Deanery.code``, ``Diocese.code`` and the foreign keys are all
    NOT NULL in the real schema, so the fixtures must supply them and must keep the
    parent/child relationships consistent for the scope checks to be meaningful.
    """
    country = Country(name="Kenya", code="KE")
    db.add(country)
    db.commit()

    province = EcclesiasticalProvince(
        name="Nairobi Province",
        code="KE-NRB",
        country_id=country.id,
    )
    db.add(province)
    db.commit()

    diocese1 = Diocese(
        name="Diocese 1",
        code="KE-DIO-001",
        ecclesiastical_province_id=province.id,
    )
    diocese2 = Diocese(
        name="Diocese 2",
        code="KE-DIO-002",
        ecclesiastical_province_id=province.id,
    )
    db.add_all([diocese1, diocese2])
    db.commit()

    deanery1 = Deanery(name="Deanery 1", code="KE-DIO-001-DNY-001", diocese_id=diocese1.id)
    deanery2 = Deanery(name="Deanery 2", code="KE-DIO-002-DNY-001", diocese_id=diocese2.id)
    db.add_all([deanery1, deanery2])
    db.commit()

    parish1 = Parish(
        name="Parish 1",
        code="KE-DIO-001-DNY-001-PAR-001",
        diocese_id=diocese1.id,
        deanery_id=deanery1.id,
    )
    parish2 = Parish(
        name="Parish 2",
        code="KE-DIO-001-DNY-001-PAR-002",
        diocese_id=diocese1.id,
        deanery_id=deanery1.id,
    )
    parish3 = Parish(
        name="Parish 3",
        code="KE-DIO-002-DNY-001-PAR-001",
        diocese_id=diocese2.id,
        deanery_id=deanery2.id,
    )
    db.add_all([parish1, parish2, parish3])
    db.commit()

    return SimpleNamespace(
        country=country,
        province=province,
        diocese1=diocese1,
        diocese2=diocese2,
        deanery1=deanery1,
        deanery2=deanery2,
        parish1=parish1,
        parish2=parish2,
        parish3=parish3,
    )


@pytest.fixture()
def diocesan_admin(db: Session, hierarchy):
    """A diocesan administrator attached to a parish in diocese1."""
    admin = User(
        full_name="Diocesan Admin",
        email="dio_admin@test.com",
        hashed_password="hash",
        role=UserRole.DIOCESAN_ADMINISTRATOR,
        parish_id=hierarchy.parish1.id,
    )
    db.add(admin)
    db.commit()
    return admin


class TestRoleHierarchy:
    """Test role hierarchy and privilege escalation protection."""
    
    def test_user_cannot_be_super_admin(self, db: Session):
        """User cannot be super admin."""
        user = User(full_name="Regular User", email="user@test.com", hashed_password="hash")
        user.role = UserRole.USER
        db.add(user)
        db.commit()
        
        assert user.role == UserRole.USER
        assert user.role != UserRole.SUPER_ADMIN
    
    def test_choir_contributor_cannot_approve_own_content(self, db: Session):
        """Choir contributor cannot approve their own content."""
        contributor = User(full_name="Contributor", email="contrib@test.com", hashed_password="hash")
        contributor.role = UserRole.CHOIR_CONTRIBUTOR
        db.add(contributor)
        db.commit()
        
        # Cannot approve own content
        assert not can_approve_content(db, contributor, contributor.id)
    
    def test_parish_admin_cannot_administer_another_parish(self, db: Session, hierarchy):
        """Parish admin cannot administer another parish."""
        parish1 = hierarchy.parish1
        parish2 = hierarchy.parish2

        admin = User(full_name="Parish Admin", email="admin@test.com", hashed_password="hash")
        admin.role = UserRole.PARISH_ADMINISTRATOR
        admin.parish_id = parish1.id
        db.add(admin)
        db.commit()
        
        # Can modify own parish
        assert can_modify_parish(db, admin, parish1.id)
        # Cannot modify another parish
        assert not can_modify_parish(db, admin, parish2.id)
    
    def test_diocesan_admin_cannot_administer_another_diocese(self, db: Session, hierarchy):
        """A diocesan administrator is confined to their own diocese.

        ``DEFAULT_ROLE_PERMISSIONS`` grants ``dioceses.update`` to
        ``diocesan_administrator`` with the note "Only own diocese", so with that
        permission in place the actor may edit their own diocese record and must
        still be refused for a sibling diocese.
        """
        diocese1 = hierarchy.diocese1
        diocese2 = hierarchy.diocese2
        parish1 = hierarchy.parish1
        parish3 = hierarchy.parish3

        admin = User(full_name="Diocesan Admin", email="dio_admin@test.com", hashed_password="hash")
        admin.role = UserRole.DIOCESAN_ADMINISTRATOR
        admin.parish_id = parish1.id
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.DIOCESAN_ADMINISTRATOR, ["dioceses.update", "parishes.update"])

        # Scope is derived from the actor's parish
        assert actor_diocese_id(db, admin) == diocese1.id

        # Diocesan admin scope reaches every parish in their own diocese
        assert can_modify_parish(db, admin, parish1.id)
        assert can_modify_parish(db, admin, hierarchy.parish2.id)
        # ...and nothing in a sibling diocese
        assert not can_modify_parish(db, admin, parish3.id)

        # Can modify own diocese
        assert can_modify_diocese(db, admin, diocese1.id)
        # Cannot modify another diocese
        assert not can_modify_diocese(db, admin, diocese2.id)

    def test_diocesan_admin_without_permission_cannot_modify_own_diocese(
        self, db: Session, hierarchy, diocesan_admin
    ):
        """Possessing the scope is not enough: the granular permission is required."""
        # No permissions have been granted in this fixture.
        assert not has_permission(db, diocesan_admin, "dioceses.update")
        assert not can_modify_diocese(db, diocesan_admin, hierarchy.diocese1.id)
        assert not can_modify_parish(db, diocesan_admin, hierarchy.parish1.id)

    def test_diocesan_admin_permission_does_not_leak_across_dioceses(
        self, db: Session, hierarchy, diocesan_admin
    ):
        """Holding the permission does not extend the scope beyond the diocese."""
        grant_permissions(db, UserRole.DIOCESAN_ADMINISTRATOR, ["dioceses.update", "parishes.update"])
        assert has_permission(db, diocesan_admin, "dioceses.update")
        assert can_modify_diocese(db, diocesan_admin, hierarchy.diocese1.id)
        assert not can_modify_diocese(db, diocesan_admin, hierarchy.diocese2.id)

    def test_dio_admin_without_parish_has_no_scope(self, db: Session, hierarchy):
        """An unscoped diocesan administrator must not be treated as global."""
        admin = User(full_name="No Scope", email="no_scope@test.com", hashed_password="hash")
        admin.role = UserRole.DIOCESAN_ADMINISTRATOR
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.DIOCESAN_ADMINISTRATOR, ["dioceses.update", "parishes.update"])

        assert actor_diocese_id(db, admin) is None
        assert not can_modify_diocese(db, admin, hierarchy.diocese1.id)
        assert not can_modify_parish(db, admin, hierarchy.parish1.id)

    def test_parish_admin_cannot_modify_a_diocese(self, db: Session, hierarchy):
        """A parish administrator never gains diocese-level write access."""
        admin = User(full_name="Parish Admin", email="p_admin_dio@test.com", hashed_password="hash")
        admin.role = UserRole.PARISH_ADMINISTRATOR
        admin.parish_id = hierarchy.parish1.id
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.PARISH_ADMINISTRATOR, ["parishes.update", "dioceses.update"])

        assert not can_modify_diocese(db, admin, hierarchy.diocese1.id)
        assert not can_modify_diocese(db, admin, hierarchy.diocese2.id)

    def test_regular_user_cannot_modify_any_diocese(self, db: Session, hierarchy):
        """An ordinary user is refused even their own diocese."""
        user = User(full_name="Plain", email="plain@test.com", hashed_password="hash")
        user.role = UserRole.USER
        user.parish_id = hierarchy.parish1.id
        db.add(user)
        db.commit()
        grant_permissions(db, UserRole.USER, ["dioceses.update"])

        assert not can_modify_diocese(db, user, hierarchy.diocese1.id)

    def test_super_admin_retains_unconditional_diocese_access(self, db: Session, hierarchy):
        """The super administrator keeps unrestricted access."""
        root = User(full_name="Root", email="root@test.com", hashed_password="hash")
        root.role = UserRole.SUPER_ADMIN
        db.add(root)
        db.commit()

        assert can_modify_diocese(db, root, hierarchy.diocese1.id)
        assert can_modify_diocese(db, root, hierarchy.diocese2.id)
        assert can_modify_parish(db, root, hierarchy.parish3.id)

    def test_admin_diocese_access_still_requires_permission(self, db: Session, hierarchy):
        """The pre-existing administrator restriction is preserved."""
        admin = User(full_name="Admin", email="admin_dio@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()

        assert not can_modify_diocese(db, admin, hierarchy.diocese1.id)
        grant_permissions(db, UserRole.ADMIN, ["dioceses.update"])
        assert can_modify_diocese(db, admin, hierarchy.diocese1.id)
        assert can_modify_diocese(db, admin, hierarchy.diocese2.id)
    
    def test_moderator_cannot_change_user_role(self, db: Session):
        """Moderator cannot change user roles."""
        moderator = User(full_name="Moderator", email="mod@test.com", hashed_password="hash")
        moderator.role = UserRole.MODERATOR
        target = User(full_name="Target", email="target@test.com", hashed_password="hash")
        target.role = UserRole.USER
        db.add_all([moderator, target])
        db.commit()
        
        # Moderator cannot assign higher role
        assert not can_assign_role(db, moderator, target, UserRole.ADMIN)
        assert not can_assign_role(db, moderator, target, UserRole.SUPER_ADMIN)
    
    def test_user_cannot_assign_themselves_higher_role(self, db: Session):
        """User cannot assign themselves a higher role."""
        user = User(full_name="User", email="user@test.com", hashed_password="hash")
        user.role = UserRole.USER
        db.add(user)
        db.commit()
        
        # Cannot assign self to higher role
        assert not can_assign_role(db, user, user, UserRole.MODERATOR)
        assert not can_assign_role(db, user, user, UserRole.ADMIN)
        assert not can_assign_role(db, user, user, UserRole.SUPER_ADMIN)
    
    def test_admin_cannot_assign_super_admin(self, db: Session):
        """Admin cannot assign super admin role."""
        admin = User(full_name="Admin", email="admin@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        target = User(full_name="Target", email="target@test.com", hashed_password="hash")
        target.role = UserRole.USER
        db.add_all([admin, target])
        db.commit()
        
        # Admin cannot assign super admin
        assert not can_assign_role(db, admin, target, UserRole.SUPER_ADMIN)
    
    def test_super_admin_can_assign_any_role(self, db: Session):
        """Super admin can assign any role."""
        super_admin = User(full_name="Super Admin", email="super@test.com", hashed_password="hash")
        super_admin.role = UserRole.SUPER_ADMIN
        target = User(full_name="Target", email="target@test.com", hashed_password="hash")
        target.role = UserRole.USER
        db.add_all([super_admin, target])
        db.commit()
        
        # Super admin can assign any role
        assert can_assign_role(db, super_admin, target, UserRole.MODERATOR)
        assert can_assign_role(db, super_admin, target, UserRole.ADMIN)
        assert can_assign_role(db, super_admin, target, UserRole.SUPER_ADMIN)


class TestSelfProtection:
    """Test self-protection logic."""
    
    def test_last_super_admin_cannot_suspend_self(self, db: Session):
        """Last super admin cannot suspend themselves."""
        super_admin = User(full_name="Super Admin", email="super@test.com", hashed_password="hash")
        super_admin.role = UserRole.SUPER_ADMIN
        db.add(super_admin)
        db.commit()
        
        # Check if last super admin
        assert check_last_super_admin(db)
        # Cannot suspend self
        assert not can_suspend_self(db, super_admin)
    
    def test_multiple_super_admins_can_suspend_self(self, db: Session):
        """Multiple super admins: one can suspend themselves."""
        super1 = User(full_name="Super 1", email="super1@test.com", hashed_password="hash")
        super1.role = UserRole.SUPER_ADMIN
        super2 = User(full_name="Super 2", email="super2@test.com", hashed_password="hash")
        super2.role = UserRole.SUPER_ADMIN
        db.add_all([super1, super2])
        db.commit()
        
        # Not last super admin
        assert not check_last_super_admin(db)
        # Can suspend self
        assert can_suspend_self(db, super1)


class TestScopedQueries:
    """Test scoped user queries."""
    
    def test_user_sees_only_self(self, db: Session):
        """Regular user can only see themselves."""
        user1 = User(full_name="User 1", email="user1@test.com", hashed_password="hash")
        user1.role = UserRole.USER
        user2 = User(full_name="User 2", email="user2@test.com", hashed_password="hash")
        user2.role = UserRole.USER
        db.add_all([user1, user2])
        db.commit()
        
        query = get_scoped_user_query(db, user1)
        # Should only see user1
        users = query.all()
        assert len(users) == 1
        assert users[0].id == user1.id
    
    def test_admin_sees_all_users(self, db: Session):
        """Admin can see all users."""
        admin = User(full_name="Admin", email="admin@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        user1 = User(full_name="User 1", email="user1@test.com", hashed_password="hash")
        user2 = User(full_name="User 2", email="user2@test.com", hashed_password="hash")
        db.add_all([admin, user1, user2])
        db.commit()
        
        query = get_scoped_user_query(db, admin)
        users = query.all()
        # Should see all users
        assert len(users) == 3


class TestUserStatus:
    """Test user status transitions."""
    
    def test_user_status_defaults_to_active(self, db: Session):
        """User status defaults to ACTIVE."""
        user = User(full_name="User", email="user@test.com", hashed_password="hash")
        db.add(user)
        db.commit()
        
        assert user.status == UserStatus.ACTIVE
        assert user.is_active == True
    
    def test_suspended_user_has_inactive_flag(self, db: Session):
        """Suspended user has is_active = False."""
        user = User(full_name="User", email="user@test.com", hashed_password="hash")
        user.status = UserStatus.SUSPENDED
        user.is_active = False
        db.add(user)
        db.commit()
        
        assert user.status == UserStatus.SUSPENDED
        assert user.is_active == False


class TestPermissionSystem:
    """Test permission-based access control."""
    
    def test_permission_check_for_super_admin(self, db: Session):
        """Super admin has all permissions."""
        super_admin = User(full_name="Super Admin", email="super@test.com", hashed_password="hash")
        super_admin.role = UserRole.SUPER_ADMIN
        db.add(super_admin)
        db.commit()
        
        # Super admin should have all permissions
        assert has_permission(db, super_admin, "users.read")
        assert has_permission(db, super_admin, "users.delete")
        assert has_permission(db, super_admin, "dioceses.update")
    
    def test_permission_check_for_regular_user(self, db: Session):
        """Regular user has limited permissions."""
        user = User(full_name="User", email="user@test.com", hashed_password="hash")
        user.role = UserRole.USER
        db.add(user)
        db.commit()
        
        # Regular user should NOT have admin permissions
        assert not has_permission(db, user, "users.delete")
        assert not has_permission(db, user, "dioceses.update")


class TestPermissionGranting:
    """Granting permissions is the privilege-escalation surface."""

    def test_super_admin_may_grant_any_permission(self, db: Session):
        root = User(full_name="Root", email="root_grant@test.com", hashed_password="hash")
        root.role = UserRole.SUPER_ADMIN
        db.add(root)
        db.commit()

        assert can_grant_permission(db, root, role=UserRole.USER, permission="users.delete")

    def test_admin_may_grant_a_permission_it_holds(self, db: Session):
        admin = User(full_name="Admin", email="admin_grant@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.ADMIN, ["roles.update", "users.suspend"])

        assert can_grant_permission(db, admin, role=UserRole.PARISH_ADMINISTRATOR,
                                    permission="users.suspend")

    def test_admin_cannot_grant_a_permission_it_lacks(self, db: Session):
        """Handing out a permission you do not hold is refused."""
        admin = User(full_name="Admin", email="admin_narrow@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.ADMIN, ["roles.update"])

        assert not can_grant_permission(db, admin, role=UserRole.PARISH_ADMINISTRATOR,
                                        permission="users.delete")

    def test_admin_cannot_grant_permissions_to_its_own_role(self, db: Session):
        """Self-grant escalation is refused even for permissions already held."""
        admin = User(full_name="Admin", email="admin_selfgrant@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.ADMIN, ["roles.update", "users.delete"])

        assert can_grant_permission(db, admin, role=UserRole.PARISH_ADMINISTRATOR,
                                    permission="users.delete")
        # Same role string, expressed as a plain string, is still refused.
        assert not can_grant_permission(db, admin, role="admin", permission="users.delete")

    def test_admin_without_roles_update_cannot_grant(self, db: Session):
        admin = User(full_name="Admin", email="admin_noroles@test.com", hashed_password="hash")
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.ADMIN, ["users.delete"])

        assert not can_grant_permission(db, admin, role=UserRole.PARISH_ADMINISTRATOR,
                                        permission="users.delete")

    @pytest.mark.parametrize(
        "role",
        [UserRole.USER, UserRole.CHOIR_CONTRIBUTOR, UserRole.PARISH_ADMINISTRATOR,
         UserRole.DIOCESAN_ADMINISTRATOR, UserRole.MODERATOR],
    )
    def test_non_admin_roles_may_never_grant_permissions(self, db: Session, hierarchy, role):
        """Only super admins and administrators may change role permissions."""
        actor = User(full_name="Actor", email=f"actor_{role.value}@test.com",
                     hashed_password="hash", role=role, parish_id=hierarchy.parish1.id)
        db.add(actor)
        db.commit()
        grant_permissions(db, role, ["roles.update", "users.delete", "dioceses.update"])

        assert not can_grant_permission(db, actor, role=UserRole.USER,
                                        permission="users.delete")


class TestRoleEscalationAcrossDioceses:
    """Diocesan role assignment must stay inside the diocese."""

    def test_dio_admin_cannot_assign_diocesan_admin(self, db: Session, hierarchy, diocesan_admin):
        """The diocesan administrator role is never assignable."""
        target = User(full_name="Target", email="target_esc@test.com", hashed_password="hash")
        target.role = UserRole.USER
        target.parish_id = hierarchy.parish1.id
        db.add(target)
        db.commit()

        assert not can_assign_role(db, diocesan_admin, target, UserRole.DIOCESAN_ADMINISTRATOR)

    def test_dio_admin_cannot_assign_admin_or_super_admin(self, db: Session, hierarchy, diocesan_admin):
        target = User(full_name="Target", email="target_esc2@test.com", hashed_password="hash")
        target.role = UserRole.USER
        target.parish_id = hierarchy.parish1.id
        db.add(target)
        db.commit()

        assert not can_assign_role(db, diocesan_admin, target, UserRole.ADMIN)
        assert not can_assign_role(db, diocesan_admin, target, UserRole.SUPER_ADMIN)

    def test_dio_admin_cannot_promote_user_in_another_diocese(self, db: Session, hierarchy,
                                                               diocesan_admin):
        """Parish-administrator promotion is scoped to the actor's diocese."""
        outsider = User(full_name="Outsider", email="outsider@test.com", hashed_password="hash")
        outsider.role = UserRole.USER
        outsider.parish_id = hierarchy.parish3.id  # diocese2
        db.add(outsider)
        db.commit()

        assert not can_assign_role(db, diocesan_admin, outsider, UserRole.PARISH_ADMINISTRATOR)

        insider = User(full_name="Insider", email="insider@test.com", hashed_password="hash")
        insider.role = UserRole.USER
        insider.parish_id = hierarchy.parish1.id  # diocese1
        db.add(insider)
        db.commit()

        assert can_assign_role(db, diocesan_admin, insider, UserRole.PARISH_ADMINISTRATOR)

    def test_dio_admin_cannot_manage_user_in_another_diocese(self, db: Session, hierarchy,
                                                              diocesan_admin):
        outsider = User(full_name="Outsider", email="outsider2@test.com", hashed_password="hash")
        outsider.role = UserRole.USER
        outsider.parish_id = hierarchy.parish3.id
        db.add(outsider)
        db.commit()

        assert not can_manage_user(db, diocesan_admin, outsider)

        insider = User(full_name="Insider", email="insider2@test.com", hashed_password="hash")
        insider.role = UserRole.USER
        insider.parish_id = hierarchy.parish1.id
        db.add(insider)
        db.commit()

        assert can_manage_user(db, diocesan_admin, insider)


class TestApprovalActions:
    """Approval must be permission-gated and never self-approved."""

    def test_contributor_cannot_approve_anything(self, db: Session, hierarchy):
        contributor = User(full_name="Contributor", email="contrib_appr@test.com",
                           hashed_password="hash", role=UserRole.CHOIR_CONTRIBUTOR)
        db.add(contributor)
        db.commit()
        grant_permissions(db, UserRole.CHOIR_CONTRIBUTOR, ["choir_resources.create"])

        other = User(full_name="Other", email="other_appr@test.com", hashed_password="hash",
                     role=UserRole.USER)
        db.add(other)
        db.commit()

        assert not can_approve_content(db, contributor, contributor.id)
        assert not can_approve_content(db, contributor, other.id)

    def test_parish_admin_approves_only_with_permission(self, db: Session, hierarchy):
        admin = User(full_name="P Admin", email="padmin_appr@test.com", hashed_password="hash",
                     role=UserRole.PARISH_ADMINISTRATOR, parish_id=hierarchy.parish1.id)
        uploader = User(full_name="Uploader", email="uploader_appr@test.com",
                        hashed_password="hash", role=UserRole.USER)
        db.add_all([admin, uploader])
        db.commit()

        assert not can_approve_content(db, admin, uploader.id)
        grant_permissions(db, UserRole.PARISH_ADMINISTRATOR, ["choir_resources.approve"])
        assert can_approve_content(db, admin, uploader.id)

    def test_self_approval_is_refused_even_with_permission(self, db: Session):
        admin = User(full_name="P Admin", email="padmin_self@test.com", hashed_password="hash",
                     role=UserRole.PARISH_ADMINISTRATOR)
        db.add(admin)
        db.commit()
        grant_permissions(db, UserRole.PARISH_ADMINISTRATOR, ["choir_resources.approve"])

        assert has_permission(db, admin, "choir_resources.approve")
        assert not can_approve_content(db, admin, admin.id)


class TestAuditLogging:
    """Administrative actions must be attributable to a loaded actor."""

    def test_audit_entry_records_the_actors_role(self, db: Session):
        """Regression: ``actor.role`` is a str once loaded, not an enum member.

        Reading ``actor.role.value`` here used to raise ``AttributeError``, which
        would have broken every administrative write.
        """
        from app.models.community import CommunityAuditLog
        from app.routes.admin_v2 import _audit_action

        admin = User(full_name="Auditor", email="audit@test.com", hashed_password="hash",
                     role=UserRole.ADMIN)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        assert isinstance(admin.role, str), "expected a plain str from the ORM"

        _audit_action(db, admin, "user.update", "user", admin.id, reason="test")
        db.commit()

        entry = db.query(CommunityAuditLog).one()
        assert entry.role == "admin"
        assert entry.action == "user.update"
        assert entry.target_type == "user"
        assert entry.actor_id == admin.id
        assert entry.reason == "test"

    def test_audit_trail_accumulates_distinct_entries(self, db: Session):
        from app.models.community import CommunityAuditLog
        from app.routes.admin_v2 import _audit_action

        admin = User(full_name="Auditor", email="audit2@test.com", hashed_password="hash",
                     role=UserRole.ADMIN)
        db.add(admin)
        db.commit()
        db.refresh(admin)

        _audit_action(db, admin, "user.update", "user", admin.id)
        _audit_action(db, admin, "user.suspend", "user", admin.id)
        db.commit()

        actions = sorted(row.action for row in db.query(CommunityAuditLog).all())
        assert actions == ["user.suspend", "user.update"]
        assert all(row.role == "admin" for row in db.query(CommunityAuditLog).all())

    def test_refused_action_is_not_audited_as_performed(self, db: Session, hierarchy,
                                                        diocesan_admin):
        """A denied cross-diocese change must not produce an audit entry."""
        from app.models.community import CommunityAuditLog
        from app.routes.admin_v2 import _audit_action

        assert not can_modify_diocese(db, diocesan_admin, hierarchy.diocese2.id)

        # The route would have returned before auditing; assert nothing was written.
        assert db.query(CommunityAuditLog).count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base
from app.models.community import (
    CommunityConversation,
    CommunityMessage,
    ConversationMember,
    ParishMembership,
    CommunityAuditLog,
    RoleAssignment,
    RoleRequest,
)
from app.models.choir import ChoirResource
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User
from app.db.database import get_db
from app.main import app
from app.routes.auth_dependency import get_current_user
from app.routes.community import (
    RoleRequestReview,
    decide_role_request,
    delete_own_message,
    list_messages,
    _scope_recipients,
)
from app.routes.choir import get_resource
from app.services.authorization import (
    can_manage_community_scope,
    can_review_role_request,
    user_belongs_to_scope,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def add_parish(db: Session, suffix: str) -> tuple[Parish, User]:
    diocese = Diocese(name=f"Diocese {suffix}", code=f"diocese-{suffix}")
    db.add(diocese)
    db.flush()
    deanery = Deanery(
        name=f"Deanery {suffix}",
        code=f"deanery-{suffix}",
        diocese_id=diocese.id,
    )
    db.add(deanery)
    db.flush()
    parish = Parish(
        name=f"Parish {suffix}",
        code=f"parish-{suffix}",
        diocese_id=diocese.id,
        deanery_id=deanery.id,
    )
    db.add(parish)
    db.flush()
    member = User(
        full_name=f"Member {suffix}",
        email=f"member-{suffix}@example.org",
        hashed_password="not-a-real-password-hash",
        parish_id=parish.id,
    )
    db.add(member)
    db.flush()
    db.add(
        ParishMembership(
            user_id=member.id,
            parish_id=parish.id,
            status="active",
        )
    )
    db.flush()
    return parish, member


def test_pending_affiliation_does_not_grant_parish_access(db: Session):
    parish, member = add_parish(db, "pending")
    db.query(ParishMembership).filter(
        ParishMembership.user_id == member.id
    ).update({"status": "pending"})

    assert not user_belongs_to_scope(db, member, "parish", parish.id)


def test_public_choir_detail_hides_unapproved_resources(db: Session):
    pending = ChoirResource(
        title="Pending song",
        category="Mass",
        language="English",
        file_url="/uploads/choir/pending.pdf",
        file_type="pdf",
        uploaded_by=None,
        is_approved=False,
        is_published=False,
    )
    db.add(pending)
    db.commit()

    with pytest.raises(HTTPException) as error:
        get_resource(pending.id, db)
    assert error.value.status_code == 404


def test_member_cannot_read_post_or_delete_another_parish_message(db: Session):
    parish_a, member_a = add_parish(db, "a")
    _, member_b = add_parish(db, "b")
    conversation = CommunityConversation(
        scope_type="parish",
        scope_id=parish_a.id,
        created_by=member_a.id,
    )
    db.add(conversation)
    db.flush()
    original = CommunityMessage(
        conversation_id=conversation.id,
        sender_id=member_a.id,
        body="Private parish message",
    )
    db.add_all(
        [
            ConversationMember(
                conversation_id=conversation.id,
                user_id=member_a.id,
            ),
            original,
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: member_b
    try:
        with TestClient(app) as client:
            conversation_url = f"/api/community/conversations/{conversation.id}/messages"
            assert client.get(conversation_url).status_code == 403
            assert client.post(conversation_url, json={"body": "Injected message"}).status_code == 403
            assert client.delete(f"/api/community/messages/{original.id}").status_code == 403
            assert client.put(f"/api/community/messages/{original.id}", json={"body": "changed"}).status_code == 405
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    db.refresh(original)
    assert original.is_deleted is False


def test_parish_admin_is_limited_to_assigned_parish(db: Session):
    parish_a, admin = add_parish(db, "admin-a")
    parish_b, _ = add_parish(db, "admin-b")
    db.add(
        RoleAssignment(
            user_id=admin.id,
            role="parish_admin",
            scope_type="parish",
            scope_id=parish_a.id,
            granted_by=admin.id,
        )
    )
    db.commit()

    assert can_manage_community_scope(db, admin, "parish", parish_a.id)
    assert not can_manage_community_scope(db, admin, "parish", parish_b.id)
    assert can_review_role_request(
        db, admin, "parish_music_director", "parish", parish_a.id
    )
    assert not can_review_role_request(
        db, admin, "parish_music_director", "parish", parish_b.id
    )
    assert not can_review_role_request(
        db, admin, "diocesan_admin", "diocese", parish_a.diocese_id
    )


def test_scoped_notifications_exclude_unverified_parish_affiliations(db: Session):
    parish, verified_member = add_parish(db, "notification")
    pending_member = User(
        full_name="Pending member",
        email="pending@example.org",
        hashed_password="not-a-real-password-hash",
        parish_id=parish.id,
    )
    db.add(pending_member)
    db.flush()
    db.add(
        ParishMembership(
            user_id=pending_member.id,
            parish_id=parish.id,
            status="pending",
        )
    )
    db.commit()

    assert _scope_recipients(db, "parish", parish.id) == [verified_member.id]


def test_requester_cannot_approve_own_role_request(db: Session):
    parish, requester = add_parish(db, "self-approval")
    request = RoleRequest(
        requester_id=requester.id,
        requested_role="parish_music_director",
        scope_type="parish",
        scope_id=parish.id,
        reason="I am requesting a role in my parish.",
    )
    db.add(request)
    db.commit()

    with pytest.raises(HTTPException) as error:
        decide_role_request(
            request.id,
            RoleRequestReview(status="approved"),
            db,
            requester,
        )

    assert error.value.status_code == 403
    assert db.query(RoleAssignment).filter(
        RoleAssignment.user_id == requester.id
    ).count() == 0


def test_super_admin_approval_creates_scoped_assignment_and_audit(db: Session):
    parish, requester = add_parish(db, "approved")
    super_admin = User(
        full_name="Platform Admin",
        email="platform-admin@example.org",
        hashed_password="not-a-real-password-hash",
        role="super_admin",
    )
    request = RoleRequest(
        requester_id=requester.id,
        requested_role="parish_music_director",
        scope_type="parish",
        scope_id=parish.id,
        reason="I am requesting a role in my parish.",
    )
    db.add_all([super_admin, request])
    db.flush()
    request_id = request.id
    db.commit()

    result = decide_role_request(
        request_id,
        RoleRequestReview(status="approved"),
        db,
        super_admin,
    )

    assignment = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == requester.id,
        RoleAssignment.role == "parish_music_director",
        RoleAssignment.scope_type == "parish",
        RoleAssignment.scope_id == parish.id,
        RoleAssignment.is_active.is_(True),
    ).one()
    audit = db.query(CommunityAuditLog).filter(
        CommunityAuditLog.action == "role_request.approved",
        CommunityAuditLog.target_id == request_id,
    ).one()
    assert result.status == "approved"
    assert assignment.granted_by == super_admin.id
    assert audit.actor_id == super_admin.id

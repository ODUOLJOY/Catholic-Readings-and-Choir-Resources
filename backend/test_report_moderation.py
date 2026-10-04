"""Security tests for the content reporting and moderation review flow.

The reporting router was previously written but never mounted, so these tests
also serve as the regression guard for that: if the router is unregistered again,
every case here fails at the client layer.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base, get_db
from app.main import app
from app.models.community import (
    CommunityAuditLog,
    CommunityConversation,
    CommunityEvent,
    CommunityGroup,
    CommunityMessage,
    ConversationMember,
    ParishMembership,
    PrayerIntention,
    RoleAssignment,
)
from app.models.report import ContentReport
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from hierarchy_test_support import build_chain, build_second_province_chain


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


def make_user(db: Session, email: str, parish=None, role: str = "user") -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        hashed_password="not-a-real-password-hash",
        role=role,
        parish_id=parish.id if parish is not None else None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    if parish is not None:
        db.add(
            ParishMembership(
                user_id=user.id,
                parish_id=parish.id,
                status="active",
            )
        )
    db.flush()
    return user


def as_user(db: Session, user: User, call):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            return call(client)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def appoint(db: Session, user: User, role: str, scope_type: str, scope_id) -> None:
    db.add(
        RoleAssignment(
            user_id=user.id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            is_active=True,
            granted_by=user.id,
        )
    )
    db.flush()


@pytest.fixture
def two_parishes(db: Session):
    """Two parishes in one diocese, plus a second diocese for isolation checks."""
    first = build_chain(db)
    second_diocese = build_second_province_chain(db)
    return {"a": first, "b": second_diocese}


def _direct_conversation(db: Session, first: User, second: User) -> CommunityConversation:
    conversation = CommunityConversation(
        conversation_type="direct",
        direct_key=f"direct:{min(first.id, second.id)}:{max(first.id, second.id)}",
        created_by=first.id,
    )
    db.add(conversation)
    db.flush()
    for member in (first, second):
        db.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=member.id,
            )
        )
    db.flush()
    return conversation


def _parish_conversation(db: Session, parish_id: int, creator: User) -> CommunityConversation:
    conversation = CommunityConversation(
        conversation_type="scope",
        scope_type="parish",
        scope_id=parish_id,
        created_by=creator.id,
    )
    db.add(conversation)
    db.flush()
    db.add(
        ConversationMember(
            conversation_id=conversation.id,
            user_id=creator.id,
        )
    )
    db.flush()
    return conversation


def _message(db: Session, conversation: CommunityConversation, sender: User, body="hi"):
    message = CommunityMessage(
        conversation_id=conversation.id,
        sender_id=sender.id,
        body=body,
    )
    db.add(message)
    db.flush()
    return message


def test_report_scopes_to_the_parish_that_owns_the_conversation(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    author = make_user(db, "author-a@example.org", parish_a)
    peer = make_user(db, "peer-a@example.org", parish_a)
    db.commit()
    conversation = _parish_conversation(db, parish_a.id, author)
    message = _message(db, conversation, peer)
    db.commit()

    response = as_user(
        db,
        author,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Abusive language",
                "description": "Repeated insults.",
                "category": "abusive_language",
            },
        ),
    )
    assert response.status_code == 201, response.text
    report = db.query(ContentReport).one()
    assert (report.scope_type, report.scope_id) == ("parish", parish_a.id)
    assert report.conversation_id == conversation.id
    assert report.category == "abusive_language"


def test_report_cannot_claim_a_wider_scope(db, two_parishes):
    """A client-supplied scope must never influence moderation routing."""
    parish_a = two_parishes["a"]["parish"]
    parish_b = two_parishes["b"]["parish"]
    author = make_user(db, "spoof-a@example.org", parish_a)
    db.commit()
    conversation = _parish_conversation(db, parish_a.id, author)
    message = _message(db, conversation, author)
    db.commit()

    response = as_user(
        db,
        author,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Trying to widen scope",
                "scope_type": "diocese",
                "scope_id": parish_b.diocese_id,
            },
        ),
    )
    assert response.status_code == 201, response.text
    report = db.query(ContentReport).one()
    assert report.scope_id == parish_a.id


def test_cannot_report_a_message_in_a_conversation_you_are_not_in(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    alice = make_user(db, "alice-priv@example.org", parish_a)
    bob = make_user(db, "bob-priv@example.org", parish_a)
    outsider = make_user(db, "outsider-priv@example.org", parish_a)
    db.commit()
    conversation = _direct_conversation(db, alice, bob)
    message = _message(db, conversation, bob, "private matter")
    db.commit()

    response = as_user(
        db,
        outsider,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Snooping",
            },
        ),
    )
    # 404, not 403: the existence of the message must stay hidden.
    assert response.status_code == 404


def test_direct_conversation_reports_are_not_routed_to_a_parish_queue(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    alice = make_user(db, "alice-direct@example.org", parish_a)
    bob = make_user(db, "bob-direct@example.org", parish_a)
    db.commit()
    conversation = _direct_conversation(db, alice, bob)
    message = _message(db, conversation, bob)
    db.commit()

    assert as_user(
        db,
        alice,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Harassment",
                "category": "harassment",
            },
        ),
    ).status_code == 201
    report = db.query(ContentReport).one()
    assert report.scope_type is None
    assert report.conversation_id == conversation.id


def test_parish_moderator_cannot_review_a_sibling_parish_report(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    parish_b = two_parishes["b"]["parish"]
    reporter = make_user(db, "reporter-b@example.org", parish_b)
    offender = make_user(db, "offender-b@example.org", parish_b)
    moderator_a = make_user(db, "moderator-a@example.org", parish_a)
    db.commit()
    appoint(db, moderator_a, "moderator", "parish", parish_a.id)

    conversation = _parish_conversation(db, parish_b.id, reporter)
    message = _message(db, conversation, offender, "rude")
    db.commit()

    created = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Rude message",
            },
        ),
    )
    assert created.status_code == 201
    report_id = created.json()["report_id"]

    denied = as_user(
        db,
        moderator_a,
        lambda client: client.get("/api/reports/"),
    )
    assert denied.status_code == 200
    assert denied.json()["total"] == 0

    decision = as_user(
        db,
        moderator_a,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "under_review"},
        ),
    )
    assert decision.status_code == 403


def test_own_parish_moderator_can_review_and_hide(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "reporter-a@example.org", parish_a)
    offender = make_user(db, "offender-a@example.org", parish_a)
    moderator = make_user(db, "moderator-own@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, offender, "rude")
    db.commit()

    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Rude message",
                "category": "abusive_language",
            },
        ),
    ).json()["report_id"]

    listing = as_user(db, moderator, lambda client: client.get("/api/reports/"))
    assert listing.status_code == 200
    body = listing.json()
    assert body["is_moderator"] is True
    assert body["total"] == 1
    # A reviewer legitimately needs the reporter to follow up.
    assert body["reports"][0]["reporter_id"] == reporter.id

    decision = as_user(
        db,
        moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={
                "status": "resolved",
                "moderation_action": "content_hidden",
                "resolution_note": "Message hid; member advised.",
            },
        ),
    )
    assert decision.status_code == 200, decision.text
    db.refresh(message)
    assert message.is_deleted is True
    actions = [
        entry.action
        for entry in db.query(CommunityAuditLog).filter(
            CommunityAuditLog.actor_id == moderator.id
        ).all()
    ]
    assert "message.hidden_by_moderation" in actions
    assert "report.resolved" in actions


def test_member_cannot_see_or_decide_another_members_report(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "reporter-priv@example.org", parish_a)
    peer = make_user(db, "peer-reports@example.org", parish_a)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()
    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Something",
            },
        ),
    ).json()["report_id"]

    listing = as_user(db, peer, lambda client: client.get("/api/reports/"))
    assert listing.status_code == 200
    assert listing.json()["total"] == 0

    assert as_user(
        db,
        peer,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "dismissed", "resolution_note": "Not my call."},
        ),
    ).status_code == 403


def test_member_sees_own_report_without_reporter_identity(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "self-reporter@example.org", parish_a)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()
    as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Correction please",
            },
        ),
    )
    listing = as_user(db, reporter, lambda client: client.get("/api/reports/"))
    payload = listing.json()
    assert payload["is_moderator"] is False
    assert payload["total"] == 1
    assert payload["reports"][0]["is_mine"] is True
    assert "reporter_id" not in payload["reports"][0]
    assert "reporter_name" not in payload["reports"][0]


def test_closing_a_report_requires_a_resolution_note(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "note-reporter@example.org", parish_a)
    moderator = make_user(db, "note-moderator@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()
    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Something",
            },
        ),
    ).json()["report_id"]

    assert as_user(
        db,
        moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "dismissed"},
        ),
    ).status_code == 422


def test_terminal_reports_cannot_be_reopened(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "terminal-reporter@example.org", parish_a)
    moderator = make_user(db, "terminal-moderator@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()
    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Something",
            },
        ),
    ).json()["report_id"]
    assert as_user(
        db,
        moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "dismissed", "resolution_note": "No violation."},
        ),
    ).status_code == 200
    assert as_user(
        db,
        moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "under_review"},
        ),
    ).status_code == 409


def test_platform_content_reports_need_a_global_appointment(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "catalog-reporter@example.org", parish_a)
    parish_moderator = make_user(db, "catalog-moderator@example.org", parish_a)
    global_moderator = make_user(db, "catalog-global@example.org")
    db.commit()
    appoint(db, parish_moderator, "moderator", "parish", parish_a.id)
    appoint(db, global_moderator, "moderator", "global", None)

    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "reading",
                "resource_id": 4242,
                "reason": "Wrong translation",
                "category": "misleading_information",
            },
        ),
    ).json()["report_id"]

    assert as_user(
        db,
        parish_moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "under_review"},
        ),
    ).status_code == 403

    assert as_user(
        db,
        global_moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "under_review"},
        ),
    ).status_code == 200


def test_duplicate_pending_report_is_not_duplicated(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "dupe-reporter@example.org", parish_a)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()

    def submit(client):
        return client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Spam",
                "category": "spam",
            },
        )

    first = as_user(db, reporter, submit)
    second = as_user(db, reporter, submit)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["duplicate"] is True
    assert second.json()["report_id"] == first.json()["report_id"]
    assert db.query(ContentReport).count() == 1


def test_unknown_resource_type_and_category_are_rejected(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    member = make_user(db, "validation@example.org", parish_a)
    db.commit()

    def submit(payload):
        return as_user(db, member, lambda client: client.post("/api/reports/", json=payload))

    assert submit(
        {
            "resource_type": "database",
            "resource_id": 1,
            "reason": "Because",
        }
    ).status_code == 422
    assert submit(
        {
            "resource_type": "message",
            "resource_id": 1,
            "reason": "Because",
            "category": "because",
        }
    ).status_code == 422
    assert submit(
        {
            "resource_type": "message",
            "resource_id": 1,
            "reason": "no",
        }
    ).status_code == 422


def test_statistics_require_moderator_authority(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    member = make_user(db, "stats-member@example.org", parish_a)
    moderator = make_user(db, "stats-moderator@example.org", parish_a)
    db.commit()
    assert as_user(db, member, lambda c: c.get("/api/reports/statistics")).status_code == 403
    appoint(db, moderator, "moderator", "parish", parish_a.id)
    assert as_user(db, moderator, lambda c: c.get("/api/reports/statistics")).status_code == 200


def test_moderator_cannot_reassign_a_report(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "assign-reporter@example.org", parish_a)
    moderator = make_user(db, "assign-moderator@example.org", parish_a)
    colleague = make_user(db, "assign-colleague@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)
    conversation = _parish_conversation(db, parish_a.id, reporter)
    message = _message(db, conversation, reporter)
    db.commit()
    report_id = as_user(
        db,
        reporter,
        lambda client: client.post(
            "/api/reports/",
            json={
                "resource_type": "message",
                "resource_id": message.id,
                "reason": "Something",
            },
        ),
    ).json()["report_id"]
    assert as_user(
        db,
        moderator,
        lambda client: client.patch(
            f"/api/reports/{report_id}",
            json={"status": "under_review", "assigned_to": colleague.id},
        ),
    ).status_code == 403


# ---------------------------------------------------------------------------
# Queue scoping
# ---------------------------------------------------------------------------


def _seed_unscoped_report(db: Session, reporter: User) -> ContentReport:
    """A direct-message report, which carries no organizational scope."""
    report = ContentReport(
        reporter_id=reporter.id,
        resource_type="message",
        resource_id=1,
        reason="Unscoped concern",
        status="pending",
    )
    db.add(report)
    db.flush()
    return report


def _seed_scoped_report(
    db: Session, reporter: User, scope_type: str, scope_id: int
) -> ContentReport:
    report = ContentReport(
        reporter_id=reporter.id,
        resource_type="message",
        resource_id=1,
        reason="Parish concern",
        status="pending",
        scope_type=scope_type,
        scope_id=scope_id,
    )
    db.add(report)
    db.flush()
    return report


def test_parish_moderator_queue_excludes_unscoped_reports(db, two_parishes):
    """A parish moderator must not see reports they cannot act on.

    ``can_review_moderation_report`` restricts unscoped reports to globally
    appointed moderators, so listing them for a parish moderator would disclose
    platform and direct-message reports outside their authority.
    """
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "queue-reporter@example.org", parish_a)
    moderator = make_user(db, "queue-moderator@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)

    scoped = _seed_scoped_report(db, reporter, "parish", parish_a.id)
    unscoped = _seed_unscoped_report(db, reporter)
    db.commit()

    body = as_user(db, moderator, lambda c: c.get("/api/reports/")).json()
    listed = {row["id"] for row in body["reports"]}
    assert listed == {scoped.id}
    assert unscoped.id not in listed
    # A member may always read back their own report.
    assert as_user(db, reporter, lambda c: c.get("/api/reports/")).json()["total"] == 2


def test_report_statistics_exclude_unscoped_reports(db, two_parishes):
    """Counts must follow the same scope filter as the queue itself."""
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "stats-scoped-reporter@example.org", parish_a)
    moderator = make_user(db, "stats-scoped-moderator@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)

    _seed_scoped_report(db, reporter, "parish", parish_a.id)
    _seed_unscoped_report(db, reporter)
    db.commit()

    body = as_user(db, moderator, lambda c: c.get("/api/reports/statistics")).json()
    assert body["total"] == 1
    assert body["by_status"] == {"pending": 1}
    assert body["is_unrestricted"] is False

    global_moderator = make_user(db, "stats-global@example.org", parish_a)
    db.commit()
    appoint(db, global_moderator, "moderator", "global", None)
    unrestricted = as_user(db, global_moderator, lambda c: c.get("/api/reports/statistics")).json()
    assert unrestricted["total"] == 2
    assert unrestricted["is_unrestricted"] is True


def test_parish_moderator_reaches_group_scoped_reports(db, two_parishes):
    """Groups inherit the parish that owns them, in the queue as in the decision.

    ``scope_contains`` already lets a parish moderator moderate a group, so the
    queue has to include the group rows or the moderator sees an empty list and
    is still authorized to open the report by id.
    """
    parish_a = two_parishes["a"]["parish"]
    reporter = make_user(db, "group-reporter@example.org", parish_a)
    moderator = make_user(db, "group-moderator@example.org", parish_a)
    db.commit()
    appoint(db, moderator, "moderator", "parish", parish_a.id)

    group = CommunityGroup(
        name="Parish youth group",
        scope_type="parish",
        scope_id=parish_a.id,
        created_by=reporter.id,
    )
    db.add(group)
    db.flush()
    report = _seed_scoped_report(db, reporter, "group", group.id)
    db.commit()

    listed = as_user(db, moderator, lambda c: c.get("/api/reports/")).json()["reports"]
    assert [row["id"] for row in listed] == [report.id]
    decision = as_user(
        db,
        moderator,
        lambda c: c.patch(
            f"/api/reports/{report.id}", json={"status": "under_review"}
        ),
    )
    assert decision.status_code == 200


def test_event_report_scopes_to_the_events_owning_parish(db, two_parishes):
    parish_a = two_parishes["a"]["parish"]
    member = make_user(db, "event-reporter@example.org", parish_a)
    outsider = make_user(db, "event-outsider@example.org", two_parishes["b"]["parish"])
    db.commit()

    event = CommunityEvent(
        organizer_id=member.id,
        title="Parish retreat",
        scope_type="parish",
        scope_id=parish_a.id,
        starts_at=datetime(2026, 5, 1, 9, 0),
        is_published=True,
    )
    db.add(event)
    db.flush()
    db.commit()

    payload = {
        "resource_type": "event",
        "resource_id": event.id,
        "reason": "Misleading details",
        "category": "misleading_information",
    }
    assert as_user(db, member, lambda c: c.post("/api/reports/", json=payload)).status_code == 201
    report = db.query(ContentReport).filter(ContentReport.resource_type == "event").one()
    assert (report.scope_type, report.scope_id) == ("parish", parish_a.id)

    # A member of another diocese cannot confirm the event exists.
    assert as_user(db, outsider, lambda c: c.post("/api/reports/", json=payload)).status_code == 404


def test_prayer_intention_report_scopes_to_the_intentions_visibility(
    db, two_parishes
):
    """Parish and diocese intentions route to that scope; private ones do not."""
    parish_a = two_parishes["a"]["parish"]
    member = make_user(db, "prayer-reporter@example.org", parish_a)
    outsider = make_user(db, "prayer-outsider@example.org", two_parishes["b"]["parish"])
    db.commit()

    parish_intention = PrayerIntention(
        user_id=member.id,
        intention="Pray for the sick",
        visibility="parish",
        parish_id=parish_a.id,
        is_active=True,
    )
    private_intention = PrayerIntention(
        user_id=member.id,
        intention="A private petition",
        visibility="private",
        is_active=True,
    )
    db.add_all([parish_intention, private_intention])
    db.flush()
    db.commit()

    parish_payload = {
        "resource_type": "prayer_intention",
        "resource_id": parish_intention.id,
        "reason": "Not appropriate",
    }
    assert as_user(db, member, lambda c: c.post("/api/reports/", json=parish_payload)).status_code == 201
    scoped = db.query(ContentReport).filter(
        ContentReport.resource_id == parish_intention.id
    ).one()
    assert (scoped.scope_type, scoped.scope_id) == ("parish", parish_a.id)

    private_payload = {
        "resource_type": "prayer_intention",
        "resource_id": private_intention.id,
        "reason": "Not appropriate",
    }
    # The owner may still report their own intention; it carries no scope.
    assert as_user(db, member, lambda c: c.post("/api/reports/", json=private_payload)).status_code == 201
    unscoped = db.query(ContentReport).filter(
        ContentReport.resource_id == private_intention.id
    ).one()
    assert unscoped.scope_type is None

    assert as_user(db, outsider, lambda c: c.post("/api/reports/", json=parish_payload)).status_code == 404

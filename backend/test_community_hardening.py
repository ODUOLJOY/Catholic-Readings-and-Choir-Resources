"""Security and behaviour tests for the hardened community routes.

These cover the abuse and access-control surface the social subsystem gained:
message editing, reactions, blocking, the suggestion state machine, and the
scoped conversation list. The isolation cases are the important ones -- they
assert that a guessed id, a spoofed scope, or an impersonated role cannot move a
caller across a parish or private-conversation boundary.
"""
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
    CommunityConversation,
    CommunityMessage,
    ConversationMember,
    MemberBlock,
    MessageReaction,
    ParishMembership,
    RoleAssignment,
)
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
                user_id=user.id, parish_id=parish.id, status="active"
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
def parishes(db: Session):
    first = build_chain(db)
    second = build_second_province_chain(db)
    return first["parish"], second["parish"]


def direct_thread(db: Session, first: User, second: User):
    conversation = CommunityConversation(
        conversation_type="direct",
        direct_key=f"direct:{min(first.id, second.id)}:{max(first.id, second.id)}",
        created_by=first.id,
    )
    db.add(conversation)
    db.flush()
    for member in (first, second):
        db.add(
            ConversationMember(conversation_id=conversation.id, user_id=member.id)
        )
    db.flush()
    return conversation


def parish_thread(db: Session, parish_id: int, creator: User):
    conversation = CommunityConversation(
        conversation_type="scope",
        scope_type="parish",
        scope_id=parish_id,
        created_by=creator.id,
    )
    db.add(conversation)
    db.flush()
    db.add(ConversationMember(conversation_id=conversation.id, user_id=creator.id))
    db.flush()
    return conversation


# --------------------------------------------------------------------------
# Message editing
# --------------------------------------------------------------------------


def test_author_can_edit_and_edit_is_recorded(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "edit-alice@example.org", parish_a)
    bob = make_user(db, "edit-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=alice.id, body="Mispelled")
    db.add(message)
    db.commit()

    response = as_user(
        db,
        alice,
        lambda client: client.patch(
            f"/api/community/messages/{message.id}", json={"body": "Misspelled"}
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_edited"] is True
    db.refresh(message)
    assert message.body == "Misspelled"
    assert message.edited_at is not None


def test_cannot_edit_another_members_message(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "own-alice@example.org", parish_a)
    bob = make_user(db, "own-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=bob.id, body="Bob's words")
    db.add(message)
    db.commit()

    response = as_user(
        db,
        alice,
        lambda client: client.patch(
            f"/api/community/messages/{message.id}", json={"body": "Rewritten by Alice"}
        ),
    )
    assert response.status_code == 403
    db.refresh(message)
    assert message.body == "Bob's words"


def test_guess_editing_a_foreign_conversation_message_is_rejected(db, parishes):
    parish_a, parish_b = parishes
    alice = make_user(db, "guess-alice@example.org", parish_a)
    bob = make_user(db, "guess-bob@example.org", parish_a)
    stranger = make_user(db, "guess-stranger@example.org", parish_b)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=bob.id, body="Private")
    db.add(message)
    db.commit()

    assert as_user(
        db,
        stranger,
        lambda client: client.patch(
            f"/api/community/messages/{message.id}", json={"body": "Tampered"}
        ),
    ).status_code == 403
    db.refresh(message)
    assert message.body == "Private"


def test_edit_requires_membership_after_removal(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "removed-alice@example.org", parish_a)
    bob = make_user(db, "removed-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=alice.id, body="Before")
    db.add(message)
    db.flush()
    db.query(ConversationMember).filter(
        ConversationMember.conversation_id == conversation.id,
        ConversationMember.user_id == alice.id,
    ).delete()
    db.commit()

    assert as_user(
        db,
        alice,
        lambda client: client.patch(
            f"/api/community/messages/{message.id}", json={"body": "After"}
        ),
    ).status_code == 403


def test_edited_message_rejects_blank_body(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "blank-alice@example.org", parish_a)
    bob = make_user(db, "blank-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=alice.id, body="Something")
    db.add(message)
    db.commit()

    assert as_user(
        db,
        alice,
        lambda client: client.patch(
            f"/api/community/messages/{message.id}", json={"body": "   "}
        ),
    ).status_code == 422


# --------------------------------------------------------------------------
# Reactions
# --------------------------------------------------------------------------


def test_reaction_lifecycle(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "react-alice@example.org", parish_a)
    bob = make_user(db, "react-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=bob.id, body="Amen")
    db.add(message)
    db.commit()

    def add(client):
        return client.post(
            f"/api/community/messages/{message.id}/reactions", json={"reaction": "amen"}
        )

    assert as_user(db, alice, add).status_code == 201
    # A second identical reaction is a conflict, not a silent duplicate.
    assert as_user(db, alice, add).status_code == 409

    listing = as_user(
        db, bob, lambda c: c.get(f"/api/community/messages/{message.id}/reactions")
    )
    assert listing.status_code == 200
    assert listing.json()["counts"] == {"amen": 1}
    # The member who reacted sees their own reactions; the other party does not.
    assert listing.json()["mine"] == []
    assert as_user(
        db, alice, lambda c: c.get(f"/api/community/messages/{message.id}/reactions")
    ).json()["mine"] == ["amen"]

    assert as_user(
        db,
        alice,
        lambda c: c.request(
            "DELETE",
            f"/api/community/messages/{message.id}/reactions",
            json={"reaction": "amen"},
        ),
    ).status_code == 200
    assert as_user(
        db, bob, lambda c: c.get(f"/api/community/messages/{message.id}/reactions")
    ).json()["counts"] == {}
    # Removing a reaction you never added must not remove someone else's.
    assert as_user(
        db,
        bob,
        lambda c: c.request(
            "DELETE",
            f"/api/community/messages/{message.id}/reactions",
            json={"reaction": "amen"},
        ),
    ).status_code == 404


def test_cannot_react_in_a_conversation_you_are_not_in(db, parishes):
    parish_a, parish_b = parishes
    alice = make_user(db, "reactscope-alice@example.org", parish_a)
    bob = make_user(db, "reactscope-bob@example.org", parish_a)
    stranger = make_user(db, "reactscope-stranger@example.org", parish_b)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    message = CommunityMessage(conversation_id=conversation.id, sender_id=bob.id, body="Hi")
    db.add(message)
    db.commit()

    assert as_user(
        db,
        stranger,
        lambda c: c.post(
            f"/api/community/messages/{message.id}/reactions", json={"reaction": "amen"}
        ),
    ).status_code == 403


# --------------------------------------------------------------------------
# Blocking
# --------------------------------------------------------------------------


def test_block_hides_the_conversation_and_stops_messaging(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "block-alice@example.org", parish_a)
    bob = make_user(db, "block-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)

    blocked = as_user(
        db, bob, lambda c: c.post("/api/community/members/block", json={"user_id": alice.id})
    )
    assert blocked.status_code == 201
    assert as_user(
        db, bob, lambda c: c.post("/api/community/members/block", json={"user_id": alice.id})
    ).status_code == 201  # idempotent
    assert db.query(MemberBlock).count() == 1

    # Bob blocked Alice, so Bob may no longer post into the thread...
    send = as_user(
        db,
        bob,
        lambda c: c.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "Let me through"},
        ),
    )
    assert send.status_code == 403
    # ...and the thread disappears from Bob's own conversation list.
    listing = as_user(db, bob, lambda c: c.get("/api/community/conversations"))
    assert listing.status_code == 200
    assert listing.json() == []

    unblock = as_user(
        db, bob, lambda c: c.delete(f"/api/community/members/block/{alice.id}")
    )
    assert unblock.status_code == 200
    assert as_user(
        db,
        bob,
        lambda c: c.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "Thank you"},
        ),
    ).status_code == 201


def test_block_hides_the_member_from_search(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "searchblock-alice@example.org", parish_a)
    bob = make_user(db, "searchblock-bob@example.org", parish_a)
    db.commit()
    as_user(db, bob, lambda c: c.post("/api/community/members/block", json={"user_id": alice.id}))
    found = as_user(db, bob, lambda c: c.get("/api/community/members", params={"q": "alice"}))
    assert found.status_code == 200
    assert all(item["id"] != alice.id for item in found.json())


def test_blocked_member_cannot_start_a_new_conversation(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "newblock-alice@example.org", parish_a)
    bob = make_user(db, "newblock-bob@example.org", parish_a)
    db.commit()
    as_user(db, alice, lambda c: c.post("/api/community/members/block", json={"user_id": bob.id}))
    assert as_user(
        db, bob, lambda c: c.post("/api/community/conversations/direct", json={"user_id": alice.id})
    ).status_code == 403


def test_cannot_block_yourself_or_an_inactive_member(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "selfblock-alice@example.org", parish_a)
    inactive = make_user(db, "inactive@example.org", parish_a)
    inactive.is_active = False
    db.commit()
    assert as_user(
        db, alice, lambda c: c.post("/api/community/members/block", json={"user_id": alice.id})
    ).status_code == 422
    assert as_user(
        db,
        alice,
        lambda c: c.post("/api/community/members/block", json={"user_id": inactive.id}),
    ).status_code == 404


def test_unblocking_someone_you_did_not_block_is_a_no_op(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "unblock-alice@example.org", parish_a)
    bob = make_user(db, "unblock-bob@example.org", parish_a)
    db.commit()
    assert as_user(
        db, alice, lambda c: c.delete(f"/api/community/members/block/{bob.id}")
    ).status_code == 200


def test_block_list_is_scoped_to_the_caller(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "blocklist-alice@example.org", parish_a)
    bob = make_user(db, "blocklist-bob@example.org", parish_a)
    carol = make_user(db, "blocklist-carol@example.org", parish_a)
    db.commit()
    as_user(db, alice, lambda c: c.post("/api/community/members/block", json={"user_id": bob.id}))
    as_user(db, alice, lambda c: c.post("/api/community/members/block", json={"user_id": carol.id}))

    listing = as_user(db, alice, lambda c: c.get("/api/community/members/blocks"))
    assert listing.status_code == 200
    body = listing.json()
    ids = {entry["user_id"] for entry in body["blocked"]}
    assert ids == {bob.id, carol.id}
    assert body["blocked_me"] == []


# --------------------------------------------------------------------------
# Conversation list isolation and paging
# --------------------------------------------------------------------------


def test_conversation_list_never_returns_another_parish_thread(db, parishes):
    parish_a, parish_b = parishes
    alice = make_user(db, "list-alice@example.org", parish_a)
    other = make_user(db, "list-other@example.org", parish_b)
    db.commit()
    thread = parish_thread(db, parish_b.id, other)

    listing = as_user(db, alice, lambda c: c.get("/api/community/conversations"))
    assert listing.status_code == 200
    assert listing.json() == []
    assert as_user(
        db, alice, lambda c: c.get(f"/api/community/conversations/{thread.id}")
    ).status_code == 403


def test_conversation_list_is_paged(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "page-alice@example.org", parish_a)
    db.commit()
    thread = parish_thread(db, parish_a.id, alice)
    as_user(
        db,
        alice,
        lambda c: c.post(
            f"/api/community/conversations/{thread.id}/messages",
            json={"body": "Hello parish"},
        ),
    )
    # Two more parish threads so paging has something to page through.
    for suffix in ("one", "two"):
        other = make_user(db, f"page-peer-{suffix}@example.org", parish_a)
        db.commit()
        peer_thread = parish_thread(db, parish_a.id, other)
        db.add(
            ConversationMember(conversation_id=peer_thread.id, user_id=alice.id)
        )
        db.commit()

    full = as_user(db, alice, lambda c: c.get("/api/community/conversations"))
    assert full.status_code == 200
    assert len(full.json()) == 3

    first = as_user(db, alice, lambda c: c.get("/api/community/conversations", params={"limit": 2}))
    assert first.status_code == 200
    assert len(first.json()) == 2
    # The second page must not repeat the first page.
    second = as_user(
        db,
        alice,
        lambda c: c.get("/api/community/conversations", params={"limit": 2, "offset": 2}),
    )
    assert len(second.json()) == 1
    assert {row["id"] for row in first.json()}.isdisjoint(
        {row["id"] for row in second.json()}
    )

    assert as_user(
        db, alice, lambda c: c.get("/api/community/conversations", params={"limit": 500})
    ).status_code == 422
    assert as_user(
        db, alice, lambda c: c.get("/api/community/conversations", params={"offset": -1})
    ).status_code == 422


def test_conversation_list_tracks_unread_and_last_message(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "unread-alice@example.org", parish_a)
    bob = make_user(db, "unread-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    as_user(
        db,
        bob,
        lambda c: c.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "Rosary at 6"},
        ),
    )
    listing = as_user(db, alice, lambda c: c.get("/api/community/conversations"))
    entry = listing.json()[0]
    assert entry["unread_count"] == 1
    assert entry["last_message"]["body"] == "Rosary at 6"
    assert entry["participant"]["id"] == bob.id

    as_user(
        db,
        alice,
        lambda c: c.post(f"/api/community/conversations/{conversation.id}/read"),
    )
    assert as_user(
        db, alice, lambda c: c.get("/api/community/conversations")
    ).json()[0]["unread_count"] == 0


def test_deleted_messages_do_not_leak_into_conversation_summaries(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "delmsg-alice@example.org", parish_a)
    bob = make_user(db, "delmsg-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)
    as_user(
        db,
        alice,
        lambda c: c.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "Please forget this"},
        ),
    )
    as_user(
        db,
        alice,
        lambda c: c.delete(f"/api/community/messages/{1}"),
    )
    assert as_user(
        db, alice, lambda c: c.get("/api/community/conversations")
    ).json()[0]["last_message"] is None


# --------------------------------------------------------------------------
# Suspicious and suspended accounts
# --------------------------------------------------------------------------


def test_a_suspended_user_cannot_send_messages(db, parishes):
    """Account suspension must stop social writes for a real authenticated session.

    The other tests override ``get_current_user``, which deliberately bypasses
    token verification. This one keeps the real dependency and sends a genuine
    access token, so it proves the suspension gate that actually guards the
    route in production.
    """
    from app.services.security import create_access_token

    parish_a, _ = parishes
    alice = make_user(db, "suspended-alice@example.org", parish_a)
    bob = make_user(db, "suspended-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)

    def post_as_bob(client):
        return client.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "Rosary meeting tomorrow"},
            headers={"Authorization": f"Bearer {create_access_token({'sub': str(bob.id)})}"},
        )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert post_as_bob(client).status_code == 201
            assert db.query(CommunityMessage).count() == 1

            bob.is_active = False
            db.commit()

            blocked = post_as_bob(client)
            assert blocked.status_code == 403
            # The blocked write must not have been persisted.
            assert db.query(CommunityMessage).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ordinary_member_cannot_reach_moderation_endpoints(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "plain@example.org", parish_a)
    admin = make_user(db, "plain-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin, "parish_admin", "parish", parish_a.id)

    # The audit log and the review queue answer 200 with nothing in them rather
    # than an error; what matters is that no entry leaks.
    audit = as_user(db, member, lambda c: c.get("/api/community/audit"))
    assert audit.status_code == 200
    assert audit.json() == []
    queue = as_user(db, member, lambda c: c.get("/api/community/suggestions/review"))
    assert queue.status_code == 200
    assert queue.json() == []
    assert as_user(
        db, member, lambda c: c.get("/api/community/role-assignments")
    ).status_code == 403
    # An appointed administrator in the same parish does see the surface.
    assert as_user(
        db, admin, lambda c: c.get("/api/community/suggestions/review")
    ).status_code == 200


def test_review_queue_only_contains_the_adminstrators_own_parish(db, parishes):
    parish_a, parish_b = parishes
    member_a = make_user(db, "queue-member-a@example.org", parish_a)
    member_b = make_user(db, "queue-member-b@example.org", parish_b)
    admin_a = make_user(db, "queue-admin-a@example.org", parish_a)
    db.commit()
    appoint(db, admin_a, "parish_admin", "parish", parish_a.id)
    mine = submit_suggestion(db, member_a, "Our parish youth programme").json()["id"]
    submit_suggestion(db, member_b, "Another parish entirely")

    queue = as_user(db, admin_a, lambda c: c.get("/api/community/suggestions/review"))
    assert queue.status_code == 200
    ids = [row["id"] for row in queue.json()]
    assert ids == [mine]


def test_diocesan_admin_sees_every_parish_in_the_diocese(db, parishes):
    """Authority resolves downward: a deanery or diocese appointment covers parishes."""
    parish_a, _ = parishes
    member_a = make_user(db, "roll-member-a@example.org", parish_a)
    member_b = make_user(db, "roll-member-b@example.org", parishes[1])
    deanery_admin = make_user(db, "roll-deanery@example.org")
    db.commit()
    appoint(db, deanery_admin, "parish_admin", "deanery", parish_a.deanery_id)
    submit_suggestion(db, member_a, "Central parish suggestion")
    submit_suggestion(db, member_b, "Mombasa suggestion")

    queue = as_user(db, deanery_admin, lambda c: c.get("/api/community/suggestions/review"))
    assert queue.status_code == 200
    bodies = {row["body"] for row in queue.json()}
    assert bodies == {"Central parish suggestion"}


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------


def submit_suggestion(db: Session, user: User, body="More youth activities"):
    return as_user(
        db,
        user,
        lambda c: c.post(
            "/api/community/suggestions",
            json={
                "category": "youth",
                "body": body,
                "scope_type": "parish",
                "scope_id": user.parish_id,
            },
        ),
    )


def test_suggestion_cannot_skip_the_state_machine(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "jump-member@example.org", parish_a)
    admin = make_user(db, "jump-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin, "parish_admin", "parish", parish_a.id)
    suggestion_id = submit_suggestion(db, member).json()["id"]

    skipped = as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "implemented", "review_note": "Done already."},
        ),
    )
    assert skipped.status_code == 409

    first = as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "under_review"},
        ),
    )
    assert first.status_code == 200
    assert first.json()["previous_status"] == "submitted"
    assert as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "accepted"},
        ),
    ).status_code == 200
    closed = as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "implemented"},
        ),
    )
    assert closed.status_code == 200
    assert closed.json()["resolved_at"] is not None
    assert as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "under_review"},
        ),
    ).status_code == 409


def test_needs_information_requires_a_note_and_stamps_escalation(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "note-member@example.org", parish_a)
    admin = make_user(db, "note-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin, "parish_admin", "parish", parish_a.id)
    suggestion_id = submit_suggestion(db, member).json()["id"]

    assert as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}", json={"status": "needs_information"}
        ),
    ).status_code == 422

    asked = as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "needs_information", "review_note": "Which age group?"},
        ),
    )
    assert asked.status_code == 200
    assert asked.json()["review_note"] == "Which age group?"

    escalated = as_user(
        db,
        admin,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}",
            json={"status": "escalated", "review_note": "Raised to the diocese."},
        ),
    )
    assert escalated.status_code == 200
    assert escalated.json()["escalated_at"] is not None


def test_suggestion_admin_cannot_touch_another_parish(db, parishes):
    parish_a, parish_b = parishes
    member_b = make_user(db, "other-member@example.org", parish_b)
    admin_a = make_user(db, "other-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin_a, "parish_admin", "parish", parish_a.id)
    suggestion_id = submit_suggestion(db, member_b).json()["id"]

    # 404 rather than 403: an administrator of another parish must not be able to
    # learn that a suggestion with this id exists in the platform at all.
    assert as_user(
        db,
        admin_a,
        lambda c: c.patch(
            f"/api/community/suggestions/{suggestion_id}", json={"status": "under_review"}
        ),
    ).status_code == 404
    assert as_user(
        db,
        admin_a,
        lambda c: c.get(f"/api/community/suggestions/{suggestion_id}"),
    ).status_code == 404
    assert as_user(
        db,
        admin_a,
        lambda c: c.post(
            f"/api/community/suggestions/{suggestion_id}/replies",
            json={"body": "Not mine to answer."},
        ),
    ).status_code == 404


def test_internal_replies_are_hidden_from_the_submitter(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "internal-member@example.org", parish_a)
    admin = make_user(db, "internal-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin, "parish_admin", "parish", parish_a.id)
    suggestion_id = submit_suggestion(db, member).json()["id"]

    as_user(
        db,
        admin,
        lambda c: c.post(
            f"/api/community/suggestions/{suggestion_id}/replies",
            json={"body": "Which age group?", "is_internal": False},
        ),
    )
    as_user(
        db,
        admin,
        lambda c: c.post(
            f"/api/community/suggestions/{suggestion_id}/replies",
            json={"body": "Budget is exhausted this quarter.", "is_internal": True},
        ),
    )

    member_view = as_user(
        db, member, lambda c: c.get(f"/api/community/suggestions/{suggestion_id}")
    )
    assert member_view.status_code == 200
    bodies = [reply["body"] for reply in member_view.json()["replies"]]
    assert bodies == ["Which age group?"]
    assert member_view.json()["can_manage"] is False

    admin_view = as_user(
        db, admin, lambda c: c.get(f"/api/community/suggestions/{suggestion_id}")
    )
    assert len(admin_view.json()["replies"]) == 2
    assert admin_view.json()["can_manage"] is True


def test_anonymous_suggestion_hides_the_submitter_from_admins(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "anon-member@example.org", parish_a)
    admin = make_user(db, "anon-admin@example.org", parish_a)
    db.commit()
    appoint(db, admin, "parish_admin", "parish", parish_a.id)
    created = as_user(
        db,
        member,
        lambda c: c.post(
            "/api/community/suggestions",
            json={
                "category": "youth",
                "body": "Please keep my name off this.",
                "scope_type": "parish",
                "scope_id": parish_a.id,
                "is_anonymous": True,
            },
        ),
    )
    assert created.status_code == 201
    detail = as_user(
        db, admin, lambda c: c.get(f"/api/community/suggestions/{created.json()['id']}")
    )
    assert detail.status_code == 200
    assert detail.json()["submitter_id"] is None
    assert detail.json()["submitter_name"] is None
    assert detail.json()["is_anonymous"] is True


def test_suggestion_scope_cannot_be_forged_to_another_parish(db, parishes):
    parish_a, parish_b = parishes
    member = make_user(db, "forge-member@example.org", parish_a)
    db.commit()
    # The caller names parish B, but the server rejects a scope they do not hold.
    response = as_user(
        db,
        member,
        lambda c: c.post(
            "/api/community/suggestions",
            json={
                "category": "youth",
                "body": "Crossing the boundary",
                "scope_type": "parish",
                "scope_id": parish_b.id,
            },
        ),
    )
    assert response.status_code == 403


def test_suggestion_detail_is_not_public(db, parishes):
    parish_a, _ = parishes
    member = make_user(db, "detail-member@example.org", parish_a)
    stranger = make_user(db, "detail-stranger@example.org", parish_a)
    db.commit()
    suggestion_id = submit_suggestion(db, member).json()["id"]
    # Existence stays hidden from uninvolved parish members.
    assert as_user(
        db, stranger, lambda c: c.get(f"/api/community/suggestions/{suggestion_id}")
    ).status_code == 404


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_rate_limit_returns_429_with_retry_after(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "limit-alice@example.org", parish_a)
    bob = make_user(db, "limit-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)

    def send(client):
        return client.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "spam"},
        )

    codes = [as_user(db, alice, send).status_code for _ in range(32)]
    assert 429 in codes
    limited = as_user(db, alice, send)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_rate_limits_are_scoped_per_member(db, parishes):
    parish_a, _ = parishes
    alice = make_user(db, "perlimit-alice@example.org", parish_a)
    bob = make_user(db, "perlimit-bob@example.org", parish_a)
    db.commit()
    conversation = direct_thread(db, alice, bob)

    def send(client):
        return client.post(
            f"/api/community/conversations/{conversation.id}/messages",
            json={"body": "spam"},
        )

    for _ in range(31):
        as_user(db, alice, send)
    assert as_user(db, alice, send).status_code == 429
    # Bob has his own allowance and must not inherit Alice's exhaustion.
    assert as_user(db, bob, send).status_code == 201

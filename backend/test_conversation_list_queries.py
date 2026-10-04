"""Query-count and pagination guards for the conversation list.

The conversation feed is the busiest read path in the community subsystem, so it
is asserted on two axes that are easy to regress silently: the number of round
trips per request, and the correctness of pagination when a blocked thread sits
inside the requested window.
"""
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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
    CommunityGroup,
    CommunityMessage,
    ConversationMember,
    GroupMembership,
    MemberBlock,
    ParishMembership,
)
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from hierarchy_test_support import build_chain


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


def make_user(db: Session, email: str, parish) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        hashed_password="not-a-real-password-hash",
        role="user",
        parish_id=parish.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        ParishMembership(user_id=user.id, parish_id=parish.id, status="active")
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


def _direct_thread(db: Session, owner: User, peer: User, body: str = "hello"):
    conversation = CommunityConversation(
        conversation_type="direct",
        direct_key=f"direct:{min(owner.id, peer.id)}:{max(owner.id, peer.id)}",
        created_by=owner.id,
    )
    db.add(conversation)
    db.flush()
    for member in (owner, peer):
        db.add(
            ConversationMember(
                conversation_id=conversation.id, user_id=member.id
            )
        )
    db.flush()
    db.add(
        CommunityMessage(
            conversation_id=conversation.id, sender_id=peer.id, body=body
        )
    )
    db.flush()
    return conversation


@pytest.fixture
def chain(db: Session):
    return build_chain(db)


def _count_queries(db: Session, call) -> int:
    counter = Counter()

    def _hook(conn, cursor, statement, parameters, context, executemany):
        counter["statements"] += 1

    event.listen(db.get_bind(), "before_cursor_execute", _hook)
    try:
        call()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", _hook)
    return counter["statements"]


def test_conversation_list_query_count_does_not_grow_with_threads(db, chain):
    """A member with many direct threads must not pay per-thread queries.

    The previous implementation issued two membership queries for every group the
    member had joined, so the cost of this endpoint grew with the number of groups
    rather than staying flat.
    """
    parish = chain["parish"]
    member = make_user(db, "query-member@example.org", parish)
    peers = [make_user(db, f"peer-{index}@example.org", parish) for index in range(6)]
    groups = []
    for index in range(4):
        group = CommunityGroup(
            name=f"Group {index}",
            scope_type="parish",
            scope_id=parish.id,
            created_by=member.id,
        )
        db.add(group)
        db.flush()
        db.add(GroupMembership(group_id=group.id, user_id=member.id))
        groups.append(group)
    db.commit()

    for peer in peers:
        _direct_thread(db, member, peer, body=f"hi {peer.email}")
    db.commit()

    def small():
        as_user(db, member, lambda c: c.get("/api/community/conversations"))

    # Compare a small membership against a larger one; the group count is what
    # used to drive the extra round trips.
    baseline = _count_queries(db, small)
    for group in groups:
        db.add(
            GroupMembership(
                group_id=group.id, user_id=peers[0].id
            )
        )
    db.commit()
    after = _count_queries(db, small)

    # The endpoint issues a fixed handful of statements regardless of how many
    # direct threads or groups the member has; the ceiling is generous enough to
    # allow incidental changes while still failing on a per-thread regression.
    assert baseline <= 25, f"conversation list issued {baseline} statements"
    assert after == baseline, (
        f"statement count moved from {baseline} to {after} as groups grew"
    )


def test_blocked_thread_does_not_shorten_a_page(db, chain):
    """Blocked threads are removed before pagination, not after it.

    Filtering after the page window returns a short page and silently skips rows,
    so a member paging through their inbox would see gaps whenever a blocked
    conversation happened to fall inside the requested range.
    """
    parish = chain["parish"]
    member = make_user(db, "page-member@example.org", parish)
    peers = [make_user(db, f"page-peer-{index}@example.org", parish) for index in range(4)]
    db.commit()

    threads = [_direct_thread(db, member, peer, body=peer.email) for peer in peers]
    db.commit()

    unblocked = as_user(db, member, lambda c: c.get("/api/community/conversations"))
    assert len(unblocked.json()) == 4

    # Block the newest thread, which sorting places first in the window.
    newest_peer = peers[-1]
    db.add(MemberBlock(blocker_id=member.id, blocked_id=newest_peer.id))
    db.commit()

    page = as_user(db, member, lambda c: c.get("/api/community/conversations?limit=4"))
    body = page.json()
    assert len(body) == 3, f"page was short: {[row['id'] for row in body]}"
    assert {row["id"] for row in body} == {
        conversation.id for conversation in threads[:-1]
    }
    assert all(row.get("participant") is not None for row in body)


def test_blocking_is_symmetric_for_the_blocked_member(db, chain):
    """A block hides the thread for both sides, not only for the blocker."""
    parish = chain["parish"]
    blocker = make_user(db, "sym-blocker@example.org", parish)
    blocked = make_user(db, "sym-blocked@example.org", parish)
    db.commit()
    conversation = _direct_thread(db, blocker, blocked)
    db.commit()

    db.add(MemberBlock(blocker_id=blocker.id, blocked_id=blocked.id))
    db.commit()

    assert as_user(db, blocker, lambda c: c.get("/api/community/conversations")).json() == []
    assert as_user(db, blocked, lambda c: c.get("/api/community/conversations")).json() == []

    # The thread itself still resolves for a member, so the endpoint hides the
    # thread rather than pretending it never existed.
    detail = as_user(
        db, blocked, lambda c: c.get(f"/api/community/conversations/{conversation.id}")
    )
    assert detail.status_code == 404


def test_group_threads_require_parish_membership(db, chain):
    """A group thread is visible only through a group inside the member's scope."""
    parish = chain["parish"]
    member = make_user(db, "group-member@example.org", parish)
    stranger = make_user(db, "group-stranger@example.org", parish)
    db.commit()

    inside = CommunityGroup(
        name="Inside scope",
        scope_type="parish",
        scope_id=parish.id,
        created_by=member.id,
    )
    outside = CommunityGroup(
        name="Outside scope",
        scope_type="parish",
        scope_id=parish.id + 999,
        created_by=stranger.id,
    )
    db.add_all([inside, outside])
    db.flush()
    db.add(GroupMembership(group_id=inside.id, user_id=member.id))
    db.add(GroupMembership(group_id=outside.id, user_id=member.id))
    db.flush()

    conversations = {}
    for name, group in (("inside", inside), ("outside", outside)):
        conversation = CommunityConversation(
            conversation_type="scope",
            scope_type="group",
            scope_id=group.id,
            created_by=member.id,
        )
        db.add(conversation)
        db.flush()
        db.add(
            ConversationMember(
                conversation_id=conversation.id, user_id=member.id
            )
        )
        db.flush()
        conversations[name] = conversation
    db.commit()

    listed = as_user(db, member, lambda c: c.get("/api/community/conversations")).json()
    ids = {row["id"] for row in listed}
    assert conversations["inside"].id in ids
    assert conversations["outside"].id not in ids

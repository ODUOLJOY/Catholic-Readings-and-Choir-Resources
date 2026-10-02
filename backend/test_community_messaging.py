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
    ConversationMember,
    MemberBlock,
    ParishMembership,
)
from app.models.user import User
from app.routes.auth_dependency import get_current_user


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


def make_user(db: Session, email: str) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        hashed_password="not-a-real-password-hash",
    )
    db.add(user)
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


def start_direct(db: Session, user: User, other_id: int):
    return as_user(
        db,
        user,
        lambda client: client.post(
            "/api/community/conversations/direct",
            json={"user_id": other_id},
        ),
    )


def test_direct_conversation_is_deduplicated(db: Session):
    alice = make_user(db, "alice@example.org")
    bob = make_user(db, "bob@example.org")
    db.commit()

    first = start_direct(db, alice, bob.id)
    assert first.status_code == 201
    conversation_id = first.json()["id"]
    assert first.json()["conversation_type"] == "direct"
    assert first.json()["participant"]["id"] == bob.id

    second = start_direct(db, bob, alice.id)
    assert second.status_code == 201
    assert second.json()["id"] == conversation_id

    assert db.query(CommunityConversation).count() == 1
    assert db.query(ConversationMember).count() == 2


def test_direct_conversation_rejects_self_and_strangers(db: Session):
    alice = make_user(db, "alice-self@example.org")
    carol = make_user(db, "carol@example.org")
    db.commit()

    self_response = start_direct(db, alice, alice.id)
    assert self_response.status_code == 400

    conversation = start_direct(db, alice, carol.id).json()

    def read_as(user, client):
        return client.get(
            f"/api/community/conversations/{conversation['id']}/messages"
        )

    assert as_user(db, carol, lambda client: read_as(carol, client)).status_code == 200

    outsider = make_user(db, "outsider@example.org")
    db.commit()
    assert as_user(
        db, outsider, lambda client: read_as(outsider, client)
    ).status_code == 403


def test_unread_counts_and_mark_read(db: Session):
    alice = make_user(db, "alice-read@example.org")
    bob = make_user(db, "bob-read@example.org")
    db.commit()

    conversation = start_direct(db, alice, bob.id).json()

    send = as_user(
        db,
        alice,
        lambda client: client.post(
            f"/api/community/conversations/{conversation['id']}/messages",
            json={"body": "Hello Bob"},
        ),
    )
    assert send.status_code == 201

    def conversations_as_bob(client):
        return client.get("/api/community/conversations")

    bob_list = as_user(db, bob, conversations_as_bob).json()
    assert len(bob_list) == 1
    assert bob_list[0]["unread_count"] == 1
    assert bob_list[0]["last_message"]["body"] == "Hello Bob"

    alice_list = as_user(db, alice, conversations_as_bob).json()
    assert alice_list[0]["unread_count"] == 0

    read = as_user(
        db,
        bob,
        lambda client: client.get(
            f"/api/community/conversations/{conversation['id']}/messages"
        ),
    )
    assert read.status_code == 200
    bob_list_after = as_user(db, bob, conversations_as_bob).json()
    assert bob_list_after[0]["unread_count"] == 0


def test_blocked_users_cannot_start_direct_conversation(db: Session):
    alice = make_user(db, "alice-block@example.org")
    bob = make_user(db, "bob-block@example.org")
    db.add(MemberBlock(blocker_id=bob.id, blocked_id=alice.id))
    db.commit()

    response = start_direct(db, alice, bob.id)
    assert response.status_code == 403


def test_member_search_is_limited_to_shared_parish(db: Session):
    from app.models.locations import Diocese
    from app.models.parish import Parish

    diocese = Diocese(name="Test Diocese", code="test-diocese")
    db.add(diocese)
    db.flush()
    parish = Parish(name="Test Parish", code="test-parish", diocese_id=diocese.id)
    other_parish = Parish(
        name="Other Parish", code="other-parish", diocese_id=diocese.id
    )
    db.add_all([parish, other_parish])
    db.flush()

    alice = make_user(db, "alice-search@example.org")
    bob = make_user(db, "bob-search@example.org")
    outsider = make_user(db, "outsider-search@example.org")
    for user in (alice, bob):
        db.add(
            ParishMembership(
                user_id=user.id, parish_id=parish.id, status="active"
            )
        )
    db.commit()

    response = as_user(
        db, alice, lambda client: client.get("/api/community/members")
    )
    assert response.status_code == 200
    ids = {member["id"] for member in response.json()}
    assert bob.id in ids
    assert alice.id not in ids
    assert outsider.id not in ids


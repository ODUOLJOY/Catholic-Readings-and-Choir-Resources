import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, decode_refresh_token
from app.db.database import Base, get_db
from app.main import app
from app.models.auth import RefreshSession
from app.models.user import User

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "SecurePassword123!"


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client, email="refresh@example.com"):
    client.post(
        "/api/auth/register",
        json={"full_name": "Refresh User", "email": email, "password": PASSWORD},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def test_login_persists_hashed_refresh_session(client, db_session):
    data = register_and_login(client)

    sessions = db_session.query(RefreshSession).all()
    assert len(sessions) == 1
    session = sessions[0]

    expected_hash = hashlib.sha256(data["refresh_token"].encode("utf-8")).hexdigest()
    assert session.token_hash == expected_hash
    assert session.revoked_at is None
    assert session.last_used_at is None

    payload = decode_refresh_token(data["refresh_token"])
    assert payload is not None
    assert session.jti == payload["jti"]
    assert str(session.user_id) == payload["sub"]


def test_refresh_rotates_and_invalidates_previous_token(client):
    first = register_and_login(client)
    original_refresh = first["refresh_token"]

    refreshed = client.post(
        "/api/auth/refresh", params={"refresh_token": original_refresh}
    )
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != original_refresh

    reused = client.post(
        "/api/auth/refresh", params={"refresh_token": original_refresh}
    )
    assert reused.status_code == 401

    rotated = client.post(
        "/api/auth/refresh", params={"refresh_token": body["refresh_token"]}
    )
    assert rotated.status_code == 200


def test_refresh_rejects_invalid_and_wrong_token_types(client):
    data = register_and_login(client)

    assert (
        client.post("/api/auth/refresh", params={"refresh_token": "not-a-token"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh", params={"refresh_token": data["access_token"]}
        ).status_code
        == 401
    )


def test_refresh_token_cannot_authenticate_requests(client):
    data = register_and_login(client)
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['refresh_token']}"},
    )
    assert response.status_code == 401


def test_logout_revokes_refresh_session(client):
    data = register_and_login(client)

    logout = client.post(
        "/api/auth/logout", json={"refresh_token": data["refresh_token"]}
    )
    assert logout.status_code == 200

    refresh = client.post(
        "/api/auth/refresh", params={"refresh_token": data["refresh_token"]}
    )
    assert refresh.status_code == 401


def test_logout_all_revokes_every_session(client):
    first = register_and_login(client, email="multi@example.com")
    second = client.post(
        "/api/auth/login",
        json={"email": "multi@example.com", "password": PASSWORD},
    ).json()

    logout_all = client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert logout_all.status_code == 200

    for token in (first["refresh_token"], second["refresh_token"]):
        assert (
            client.post("/api/auth/refresh", params={"refresh_token": token}).status_code
            == 401
        )


def test_refresh_rejects_disabled_account(client, db_session):
    data = register_and_login(client)
    user = db_session.query(User).filter(User.email == "refresh@example.com").one()
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/auth/refresh", params={"refresh_token": data["refresh_token"]}
    )
    assert response.status_code == 403


def test_expired_refresh_session_is_rejected(client, db_session):
    data = register_and_login(client)
    session = db_session.query(RefreshSession).one()
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    response = client.post(
        "/api/auth/refresh", params={"refresh_token": data["refresh_token"]}
    )
    assert response.status_code == 401

    db_session.refresh(session)
    assert session.revoked_at is not None


def test_expired_access_token_is_rejected(client):
    data = register_and_login(client)
    expired = create_access_token(
        data={"sub": "1", "role": "user"},
        expires_delta=timedelta(seconds=-5),
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


def test_change_password_revokes_sessions(client):
    data = register_and_login(client)
    changed = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {data['access_token']}"},
        json={"current_password": PASSWORD, "new_password": "NewSecurePassword456!"},
    )
    assert changed.status_code == 200

    response = client.post(
        "/api/auth/refresh", params={"refresh_token": data["refresh_token"]}
    )
    assert response.status_code == 401

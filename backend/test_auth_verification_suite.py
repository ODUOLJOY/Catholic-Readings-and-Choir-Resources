"""Comprehensive auth verification coverage for the seven required test areas.

Uses isolated in-memory SQLite and synthetic accounts only.
Never prints tokens or secrets.
"""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, verify_password
from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.auth import ExternalIdentity
from app.models.user import User
from app.services import google_auth
from app.services.auth_service import generate_reset_token
from app.services.google_auth import GoogleIdentity

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "SecurePassword123!"
NEW_PASSWORD = "BrandNewPassword456!"
CLIENT_ID = "test-client.apps.googleusercontent.com"
REDIRECT_URI = "https://app.example.com/auth/google/callback"


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


def register(client, email="user@example.com", password=PASSWORD, name="Test User"):
    return client.post(
        "/api/auth/register",
        json={"full_name": name, "email": email, "password": password},
    )


def login(client, email="user@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def enable_google(monkeypatch, resolved: GoogleIdentity):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "")

    def fake_verify(id_token_value, *, audience=None):
        return resolved

    monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)


# ---------------------------------------------------------------------------
# TEST 2 — Email/password login
# ---------------------------------------------------------------------------


def test_unknown_email_rejected_without_distinction(client):
    response = login(client, email="nobody@example.com")
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_malformed_email_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": PASSWORD},
    )
    assert response.status_code == 422


def test_short_password_rejected_on_register(client):
    response = register(client, email="short@example.com", password="short")
    assert response.status_code == 422


def test_password_is_hashed_not_plaintext(client, db_session):
    assert register(client).status_code == 201
    user = db_session.query(User).filter(User.email == "user@example.com").one()
    assert user.hashed_password != PASSWORD
    assert verify_password(PASSWORD, user.hashed_password)
    assert not verify_password("WrongPassword123!", user.hashed_password)


def test_unverified_account_can_login_per_current_policy(client, db_session):
    """Current policy: email/password login does not require verification."""
    assert register(client).status_code == 201
    user = db_session.query(User).filter(User.email == "user@example.com").one()
    assert user.is_verified is False
    response = login(client)
    assert response.status_code == 200
    assert response.json()["access_token"]


# ---------------------------------------------------------------------------
# TEST 3 / 4 — Role enforcement and Google role assignment
# ---------------------------------------------------------------------------


def test_forged_admin_claim_cannot_access_admin_dashboard(client, db_session):
    assert register(client).status_code == 201
    user = db_session.query(User).filter(User.email == "user@example.com").one()
    forged = create_access_token(
        data={"sub": str(user.id), "role": "super_admin"},
    )
    response = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert response.status_code == 403


def test_ordinary_user_token_cannot_access_admin_dashboard(client):
    assert register(client).status_code == 201
    tokens = login(client).json()
    response = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_super_admin_from_db_role_can_access_dashboard(client, db_session):
    assert register(client, email="admin@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "admin@example.com").one()
    user.role = "super_admin"
    user.is_verified = True
    db_session.commit()

    tokens = login(client, email="admin@example.com").json()
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["role"] == "super_admin"

    dashboard = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert dashboard.status_code == 200


def test_google_profile_cannot_overwrite_existing_role(client, db_session, monkeypatch):
    assert register(client, email="keeper@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "keeper@example.com").one()
    user.role = "user"
    user.is_verified = True
    user.full_name = "Trusted Name"
    db_session.commit()
    original_id = user.id

    enable_google(
        monkeypatch,
        GoogleIdentity(
            subject="google-keeper",
            email="keeper@example.com",
            email_verified=True,
            name="Attacker Name",
            picture="https://evil.example/x.png",
        ),
    )
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 200

    db_session.expire_all()
    linked = db_session.query(User).filter(User.id == original_id).one()
    assert linked.role == "user"
    assert linked.full_name == "Trusted Name"
    assert db_session.query(User).count() == 1
    assert db_session.query(ExternalIdentity).count() == 1


# ---------------------------------------------------------------------------
# TEST 5 — Session / protected access (API layer)
# ---------------------------------------------------------------------------


def test_unauthenticated_me_rejected(client):
    assert client.get("/api/auth/me").status_code == 401


def test_malformed_bearer_rejected(client):
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        ).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# TEST 6 — Refresh isolation / concurrent refresh
# ---------------------------------------------------------------------------


def test_refresh_token_cannot_invalidate_another_users_session(client, db_session):
    assert register(client, email="alice@example.com").status_code == 201
    assert register(client, email="bob@example.com").status_code == 201
    alice = login(client, email="alice@example.com").json()
    bob = login(client, email="bob@example.com").json()

    # Invalid/forged use of alice token against bob's identity is not possible
    # via API; ensure bob's session remains valid after alice logout.
    assert (
        client.post(
            "/api/auth/logout", json={"refresh_token": alice["refresh_token"]}
        ).status_code
        == 200
    )
    still_bob = client.post(
        "/api/auth/refresh", json={"refresh_token": bob["refresh_token"]}
    )
    assert still_bob.status_code == 200
    assert still_bob.json()["refresh_token"] != bob["refresh_token"]


def test_sequential_refresh_reuse_is_rejected(client):
    """True multi-threaded concurrency is not safely exercisable with the shared
    TestClient session fixture; sequential reuse still proves rotation policy.
    """
    assert register(client).status_code == 201
    tokens = login(client).json()
    first = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200
    reused = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401


# ---------------------------------------------------------------------------
# TEST 7 — Password reset + verification email mocking
# ---------------------------------------------------------------------------


def test_password_reset_one_time_and_revokes_sessions(client, db_session, monkeypatch):
    import app.routes.auth as auth_routes

    assert register(client, email="reset@example.com").status_code == 201
    first_login = login(client, email="reset@example.com").json()

    captured = {}

    def fake_send(recipient, token):
        captured["recipient"] = recipient
        captured["token"] = token

    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    monkeypatch.setattr(auth_routes, "send_password_reset_email", fake_send)

    forgot = client.post(
        "/api/auth/forgot-password", json={"email": "reset@example.com"}
    )
    assert forgot.status_code == 200
    assert captured["token"]

    user = db_session.query(User).filter(User.email == "reset@example.com").one()
    token_hash = hashlib.sha256(captured["token"].encode("utf-8")).hexdigest()
    assert user.password_reset_token == token_hash

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": captured["token"], "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200

    # Old refresh session revoked
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": first_login["refresh_token"]},
        ).status_code
        == 401
    )

    # Old password fails; new works
    assert login(client, email="reset@example.com").status_code == 401
    assert (
        login(client, email="reset@example.com", password=NEW_PASSWORD).status_code
        == 200
    )

    # Reuse reset token fails
    reuse = client.post(
        "/api/auth/reset-password",
        json={"token": captured["token"], "password": "AnotherPassword789!"},
    )
    assert reuse.status_code == 400


def test_reset_rejects_unissued_token(client, db_session):
    assert register(client, email="reset2@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "reset2@example.com").one()
    forged = generate_reset_token(user)
    response = client.post(
        "/api/auth/reset-password",
        json={"token": forged, "password": NEW_PASSWORD},
    )
    assert response.status_code == 400


def test_verification_email_delivery_failure_keeps_account_unverified(
    client, db_session, monkeypatch
):
    import app.routes.auth as auth_routes
    from app.services.email import EmailDeliveryError

    def boom(recipient, token):
        raise EmailDeliveryError("smtp down")

    monkeypatch.setattr(auth_routes, "send_email_verification_email", boom)
    response = register(client, email="mailfail@example.com")
    assert response.status_code == 201
    user = db_session.query(User).filter(User.email == "mailfail@example.com").one()
    assert user.is_verified is False

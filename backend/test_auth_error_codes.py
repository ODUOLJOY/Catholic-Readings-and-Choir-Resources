"""
§10 — Stable application error codes on authentication-flow errors.

The backend must attach a stable, machine-readable ``code`` to every error it
returns during registration, login, token refresh, password reset, email
verification and Google sign-in. These tests assert the code lives alongside
the existing human-readable ``detail`` (so older clients keep working) and
that the status code is unchanged.

No real credentials, tokens or secrets are asserted on.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

COMMON_USER = {
    "full_name": "Auth Code User",
    "email": "authcodes@example.com",
    "password": "SecurePassword123!",
}


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
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client, email=COMMON_USER["email"]):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": COMMON_USER["full_name"],
            "email": email,
            "password": COMMON_USER["password"],
        },
    )


def _login(client, email=COMMON_USER["email"], password=COMMON_USER["password"]):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def test_duplicate_email_carries_error_code(client):
    assert _register(client).status_code == 201

    dup = _register(client)
    assert dup.status_code == 400
    body = dup.json()
    # detail preserved for backward compatibility
    assert "detail" in body
    assert "already registered" in body["detail"].lower()
    assert body["code"] == "AUTH_EMAIL_ALREADY_EXISTS"


def test_invalid_credentials_carry_error_code(client):
    _register(client)

    # Wrong password: same generic detail as a bad email (no enumeration).
    bad_pw = _login(client, password="WrongPassword123!")
    assert bad_pw.status_code == 401
    body = bad_pw.json()
    assert body["detail"] == "Invalid email or password."
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"

    bad_email = _login(client, email="no-such-user@example.com", password="WrongPassword123!")
    assert bad_email.status_code == 401
    assert bad_email.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_unauthenticated_me_carries_error_code(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert "detail" in body
    assert body["code"] == "AUTH_UNAUTHENTICATED"


def test_admin_endpoint_enforces_role_server_side(client):
    _register(client)
    token = _login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # A plain "user" must be refused on admin endpoints — server-side only.
    response = client.get("/api/admin/dashboard", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_INSUFFICIENT_ROLE"


def test_invalid_refresh_token_carries_error_code(client):
    response = client.post(
        "/api/auth/refresh",
        params={"refresh_token": "not-a-real-token"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_INVALID_REFRESH_TOKEN"


def test_non_auth_errors_omit_code_by_default(client):
    # A 404 for an unknown route is not an auth-flow error and must keep the
    # default FastAPI shape (no synthesized code).
    response = client.get("/api/definitely-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "code" not in body
    assert "detail" in body

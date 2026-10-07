"""Phase 11 — CORS regression tests for the authentication + liturgy endpoints.

The originally reported browser failures were CORS errors on:

  * GET  /api/v1/liturgy/today      (no Access-Control-Allow-Origin)
  * POST /api/auth/login            (500, hidden behind a CORS fault)
  * GET  /api/auth/me               (401, unconfirmed)
  * GET  /api/community/me          (401, unconfirmed)

These tests pin down exactly those responses from the local Expo web origins
``http://localhost:8081`` and ``http://127.0.0.1:8081`` -- including on 401 /
422 / 500 responses, so a server error is never mis-reported to the browser as
a CORS failure. Disallowed origins are never echoed and a wildcard is never
emitted (credentials are enabled).

No real credentials or secrets are used; everything runs against an in-memory
SQLite database.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app

LOCAL_ORIGIN = "http://localhost:8081"
LOOPBACK_ORIGIN = "http://127.0.0.1:8081"
DISALLOWED_ORIGIN = "https://evil.example.net"

EMAIL = "corsuser@example.com"
PASSWORD = "SecurePassword123!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # raise_server_exceptions=False exercises the application's own unhandled
    # exception handler -- the exact path the browser receives on a 500.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(client, email=EMAIL, password=PASSWORD):
    return client.post(
        "/api/auth/register",
        json={"full_name": "CORS User", "email": email, "password": password},
    )


def _login(client, email=EMAIL, password=PASSWORD, origin=LOCAL_ORIGIN):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": origin},
    )


# ---------------------------------------------------------------------------
# 1. GET /api/v1/liturgy/today with Origin: http://localhost:8081
# ---------------------------------------------------------------------------


def test_liturgy_today_carries_cors_for_local_origin(client):
    response = client.get("/api/v1/liturgy/today", headers={"Origin": LOCAL_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert isinstance(response.json()["readings"], list)


# ---------------------------------------------------------------------------
# 2. POST /api/auth/login with Origin: http://localhost:8081, invalid creds
# ---------------------------------------------------------------------------


def test_login_with_invalid_credentials_still_carries_cors(client):
    response = _login(client, email="nobody@example.com", password="WrongPassword123!")
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# 3. Successful login from an allowed origin
# ---------------------------------------------------------------------------


def test_successful_login_and_me_carry_cors(client):
    assert _register(client).status_code == 201

    login = _login(client)
    assert login.status_code == 200
    assert login.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert login.headers["access-control-allow-credentials"] == "true"
    body = login.json()
    assert body["access_token"] and body["refresh_token"]

    me = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {body['access_token']}",
            "Origin": LOCAL_ORIGIN,
        },
    )
    assert me.status_code == 200
    assert me.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert me.json()["email"] == EMAIL


# ---------------------------------------------------------------------------
# 4. 401 /api/auth/me carries CORS
# ---------------------------------------------------------------------------


def test_me_without_token_carries_cors(client):
    response = client.get("/api/auth/me", headers={"Origin": LOCAL_ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert response.json()["code"] == "AUTH_UNAUTHENTICATED"


def test_community_me_without_token_carries_cors(client):
    response = client.get("/api/community/me", headers={"Origin": LOCAL_ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


# ---------------------------------------------------------------------------
# 6. OPTIONS preflight for /api/auth/login
# ---------------------------------------------------------------------------


def test_login_preflight_returns_cors_headers(client):
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": LOCAL_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"]


# ---------------------------------------------------------------------------
# Validation / malformed payload still carries CORS
# ---------------------------------------------------------------------------


def test_login_malformed_email_carries_cors_and_returns_422(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": PASSWORD},
        headers={"Origin": LOCAL_ORIGIN},
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


# ---------------------------------------------------------------------------
# Loopback origin 127.0.0.1:8081 is allowed
# ---------------------------------------------------------------------------


def test_loopback_origin_is_allowed(client):
    response = _login(
        client,
        email="nobody@example.com",
        password="WrongPassword123!",
        origin=LOOPBACK_ORIGIN,
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == LOOPBACK_ORIGIN


# ---------------------------------------------------------------------------
# Unhandled 500 must not be reported to the browser as a CORS fault
# ---------------------------------------------------------------------------


def test_login_500_is_not_reported_as_a_cors_failure(client, engine):
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE users"))
        connection.commit()

    response = _login(client, email="nobody@example.com", password="WrongPassword123!")
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal server error."}


# ---------------------------------------------------------------------------
# 7. Disallowed origin must NOT be blindly allowed
# ---------------------------------------------------------------------------


def test_disallowed_origin_is_never_echoed(client):
    response = _login(
        client,
        email="nobody@example.com",
        password="WrongPassword123!",
        origin=DISALLOWED_ORIGIN,
    )
    assert response.status_code == 401
    assert "access-control-allow-origin" not in response.headers


def test_lan_origin_allowed_only_when_opted_in(client):
    """A phone/tablet on the same Wi-Fi may reach a 0.0.0.0-bound dev server only
    when the operator explicitly sets ALLOW_LAN_ORIGINS=True. With the flag off
    the private origin is rejected exactly like any other non-loopback origin.
    """
    from app.core.config import settings as _settings

    lan_origin = "http://192.168.1.50:8081"
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": lan_origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    if _settings.ALLOW_LAN_ORIGINS:
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == lan_origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers

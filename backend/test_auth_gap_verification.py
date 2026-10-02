"""Gap-closing verification tests for the seven authentication test areas.

Isolated in-memory / temporary SQLite databases and synthetic accounts only.
No credential values, tokens, or secrets are printed or asserted on directly.
"""
import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import ALGORITHM, create_access_token, create_refresh_token
from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.auth import ExternalIdentity, RefreshSession
from app.models.user import User
from app.services import auth_service, google_auth
from app.services.google_auth import GoogleAuthError, GoogleIdentity

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "SecurePassword123!"
CLIENT_ID = "test-client.apps.googleusercontent.com"
CLIENT_SECRET = "test-only-client-secret"
REDIRECT_URI = "https://app.example.com/auth/google"


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


def identity(subject="gap-subject", email="gap@example.com", name="Gap User"):
    return GoogleIdentity(
        subject=subject,
        email=email,
        email_verified=True,
        name=name,
        picture=None,
    )


def enable_google(monkeypatch, resolved=None):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "")
    if resolved is not None:

        def fake_verify(id_token_value, *, audience=None):
            return resolved

        monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)


def register(client, email="gapuser@example.com"):
    return client.post(
        "/api/auth/register",
        json={"full_name": "Gap User", "email": email, "password": PASSWORD},
    )


def mint_expired_token(token_type: str, subject: str) -> str:
    """Mint an already-expired token to exercise the expiry path only.

    The value is never logged or printed.
    """
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# TEST 1 - Google sign-in: previously unexercised callback and error paths
# ---------------------------------------------------------------------------


def test_google_callback_rejects_failed_code_exchange(
    client, db_session, monkeypatch
):
    enable_google(monkeypatch, identity())

    def failing_exchange(code, redirect_uri):
        raise GoogleAuthError("Code exchange rejected.")

    monkeypatch.setattr(google_auth, "exchange_google_code", failing_exchange)

    state = google_auth.create_google_state()
    response = client.post(
        "/api/auth/google/callback",
        json={"code": "abc123", "redirect_uri": REDIRECT_URI, "state": state},
    )
    assert response.status_code == 401
    assert db_session.query(ExternalIdentity).count() == 0
    assert db_session.query(User).count() == 0


def test_google_callback_rejects_disallowed_redirect_uri(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setattr(
        settings,
        "GOOGLE_ALLOWED_REDIRECT_URIS",
        "https://app.example.com/auth/google",
    )

    state = google_auth.create_google_state()
    response = client.post(
        "/api/auth/google/callback",
        json={
            "code": "abc123",
            "redirect_uri": "https://evil.example.com/auth/google",
            "state": state,
        },
    )
    assert response.status_code == 400


def test_google_callback_rejects_expired_state(client, monkeypatch):
    enable_google(monkeypatch, identity())

    expired_state = jwt.encode(
        {
            "type": google_auth.GOOGLE_STATE_TYPE,
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(seconds=30),
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.post(
        "/api/auth/google/callback",
        json={"code": "abc123", "redirect_uri": REDIRECT_URI, "state": expired_state},
    )
    assert response.status_code == 400


def test_google_endpoints_return_503_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    assert client.get("/api/auth/google/config").status_code == 200
    assert (
        client.get(
            "/api/auth/google/authorization-url",
            params={"redirect_uri": REDIRECT_URI},
        ).status_code
        == 503
    )
    assert client.post("/api/auth/google", json={"id_token": "x" * 32}).status_code == 503
    assert (
        client.post(
            "/api/auth/google/callback",
            json={
                "code": "abc123",
                "redirect_uri": REDIRECT_URI,
                "state": "some-state",
            },
        ).status_code
        == 503
    )


def test_google_config_never_exposes_client_secret(client, monkeypatch):
    enable_google(monkeypatch, identity())
    response = client.get("/api/auth/google/config")
    assert response.status_code == 200
    assert set(response.json()) == {"enabled", "client_id"}
    assert CLIENT_SECRET not in response.text
    assert "secret" not in response.text.lower()


def test_google_sign_in_ignores_client_supplied_role(client, db_session, monkeypatch):
    enable_google(monkeypatch, identity())

    response = client.post(
        "/api/auth/google",
        json={
            "id_token": "x" * 32,
            "role": "super_admin",
            "is_super_admin": True,
            "user": {"role": "super_admin"},
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "user"

    user = db_session.query(User).filter(User.email == "gap@example.com").one()
    assert user.role == "user"


# ---------------------------------------------------------------------------
# TEST 3 / TEST 5 - Server-side authorization of protected endpoints
# ---------------------------------------------------------------------------


def test_admin_endpoint_rejects_unauthenticated_request(client):
    assert client.get("/api/admin/dashboard").status_code == 401


def test_admin_endpoint_rejects_malformed_bearer(client):
    assert (
        client.get(
            "/api/admin/dashboard",
            headers={"Authorization": "Bearer not.a.jwt"},
        ).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# Regression for a confirmed defect: the resolver re-exported by the public
# facade app/services/auth.py previously raised an unhandled ValueError /
# KeyError (HTTP 500) for a malformed or missing "sub" claim and did not
# reject disabled accounts.
# ---------------------------------------------------------------------------


def test_auth_service_resolver_rejects_malformed_subject(db_session):
    token = create_access_token(data={"sub": "not-an-int", "role": "user"})
    with pytest.raises(HTTPException) as error:
        auth_service.get_current_user(db_session, token)
    assert error.value.status_code == 401


def test_auth_service_resolver_rejects_missing_subject(db_session):
    token = create_access_token(data={"role": "super_admin"})
    with pytest.raises(HTTPException) as error:
        auth_service.get_current_user(db_session, token)
    assert error.value.status_code == 401


def test_auth_service_resolver_rejects_disabled_account(client, db_session):
    assert register(client, email="disabledresolver@example.com").status_code == 201
    user = (
        db_session.query(User)
        .filter(User.email == "disabledresolver@example.com")
        .one()
    )
    user.is_active = False
    db_session.commit()

    token = create_access_token(data={"sub": str(user.id), "role": "user"})
    with pytest.raises(HTTPException) as error:
        auth_service.get_current_user(db_session, token)
    assert error.value.status_code == 403


# ---------------------------------------------------------------------------
# TEST 6 - Refresh-token rotation under genuinely concurrent use
# ---------------------------------------------------------------------------


def test_concurrent_refresh_does_not_replay_a_rotated_token(tmp_path):
    """Two threads present the same refresh token simultaneously.

    Invariant asserted: the presented token is never left reusable and no more
    than one rotation is granted for it.
    """
    db_path = tmp_path / "concurrency.sqlite"
    file_engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    FileSession = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)
    Base.metadata.create_all(bind=file_engine)

    from app.routes.auth import refresh_token as refresh_route

    try:
        session = FileSession()
        try:
            user = User(
                full_name="Concurrent User",
                email="concurrent@example.com",
                hashed_password=auth_service.hash_password(PASSWORD),
                role="user",
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            session.commit()

            jti = str(uuid.uuid4())
            original = create_refresh_token(
                data={"sub": str(user.id)}, jti=jti
            )
            session.add(
                RefreshSession(
                    user_id=user.id,
                    token_hash=hashlib.sha256(
                        original.encode("utf-8")
                    ).hexdigest(),
                    jti=jti,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            session.commit()
        finally:
            session.close()

        def attempt(_ignored):
            worker = FileSession()
            try:
                result = refresh_route(refresh_token=original, db=worker)
                worker.commit()
                return 200
            except HTTPException as error:
                worker.rollback()
                return error.status_code
            except Exception:  # noqa: BLE001 - lock contention is a safe reject
                worker.rollback()
                return "rejected"
            finally:
                worker.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))

        successes = [code for code in results if code == 200]
        assert len(successes) == 1, (
            "expected exactly one rotation to succeed, got " f"{results}"
        )

        verifier = FileSession()
        try:
            with pytest.raises(HTTPException) as error:
                refresh_route(refresh_token=original, db=verifier)
            assert error.value.status_code == 401
        finally:
            verifier.close()
    finally:
        Base.metadata.drop_all(bind=file_engine)
        file_engine.dispose()


# ---------------------------------------------------------------------------
# TEST 7 - Expiry of reset and verification tokens
# ---------------------------------------------------------------------------


def test_expired_reset_token_is_rejected(client, db_session):
    assert register(client, email="expiryreset@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "expiryreset@example.com").one()

    expired = mint_expired_token("reset", str(user.id))
    user.password_reset_token = hashlib.sha256(expired.encode("utf-8")).hexdigest()
    db_session.commit()

    response = client.post(
        "/api/auth/reset-password",
        json={"token": expired, "password": "AnotherSecure123!"},
    )
    assert response.status_code == 401

    db_session.expire_all()
    still = db_session.query(User).filter(User.email == "expiryreset@example.com").one()
    assert auth_service.verify_password(PASSWORD, still.hashed_password) is True


def test_expired_verification_token_is_rejected(client, db_session):
    assert register(client, email="expiryverify@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "expiryverify@example.com").one()

    expired = mint_expired_token("verify", str(user.id))
    user.email_verification_token = hashlib.sha256(
        expired.encode("utf-8")
    ).hexdigest()
    db_session.commit()

    response = client.post("/api/auth/verify-email", params={"token": expired})
    assert response.status_code == 401

    db_session.expire_all()
    still = db_session.query(User).filter(User.email == "expiryverify@example.com").one()
    assert still.is_verified is False


def test_access_token_cannot_be_used_as_reset_token(client, db_session):
    assert register(client, email="crossuse@example.com").status_code == 201
    user = db_session.query(User).filter(User.email == "crossuse@example.com").one()

    access = create_access_token(data={"sub": str(user.id), "role": "user"})
    response = client.post(
        "/api/auth/reset-password",
        json={"token": access, "password": "AnotherSecure123!"},
    )
    assert response.status_code == 400
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.auth import ExternalIdentity
from app.models.user import User
from app.services import google_auth
from app.services.google_auth import GoogleAuthError, GoogleIdentity

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "SecurePassword123!"
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


def identity(
    subject="google-subject-1",
    email="newgoogle@example.com",
    email_verified=True,
    name="New Google",
    picture=None,
):
    return GoogleIdentity(
        subject=subject,
        email=email,
        email_verified=email_verified,
        name=name,
        picture=picture,
    )


def enable_google(monkeypatch, resolved=None):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "")
    if resolved is not None:

        def fake_verify(id_token_value, *, audience=None):
            return resolved

        monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)


def test_config_reports_disabled_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    response = client.get("/api/auth/google/config")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["client_id"] == ""


def test_config_reports_client_id_when_configured(client, monkeypatch):
    enable_google(monkeypatch, identity())
    response = client.get("/api/auth/google/config")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["client_id"] == CLIENT_ID


def test_google_sign_in_creates_verified_user_and_identity(
    client, db_session, monkeypatch
):
    enable_google(monkeypatch, identity())

    response = client.post(
        "/api/auth/google", json={"id_token": "x" * 32}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]

    user = db_session.query(User).filter(User.email == "newgoogle@example.com").one()
    assert user.role == "user"
    assert user.is_verified is True
    assert user.hashed_password

    links = db_session.query(ExternalIdentity).all()
    assert len(links) == 1
    assert links[0].provider == "google"
    assert links[0].provider_subject == "google-subject-1"


def test_google_sign_in_is_idempotent(client, db_session, monkeypatch):
    enable_google(monkeypatch, identity())

    first = client.post("/api/auth/google", json={"id_token": "x" * 32})
    second = client.post("/api/auth/google", json={"id_token": "y" * 32})
    assert first.status_code == 200
    assert second.status_code == 200

    assert db_session.query(ExternalIdentity).count() == 1
    assert db_session.query(User).count() == 1


def test_google_sign_in_rejects_unverified_email(client, monkeypatch):
    enable_google(monkeypatch, identity(email_verified=False))
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 400


def test_google_sign_in_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 503


def test_google_sign_in_rejects_invalid_token(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)

    def fake_verify(id_token_value, *, audience=None):
        raise GoogleAuthError("Invalid Google identity token.")

    monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 401


def test_google_links_only_verified_local_account(client, db_session, monkeypatch):
    client.post(
        "/api/auth/register",
        json={"full_name": "Existing", "email": "linked@example.com", "password": PASSWORD},
    )
    user = db_session.query(User).filter(User.email == "linked@example.com").one()
    user.is_verified = True
    db_session.commit()

    enable_google(monkeypatch, identity(email="linked@example.com"))
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 200

    db_session.expire_all()
    users = db_session.query(User).filter(User.email == "linked@example.com").all()
    assert len(users) == 1
    assert users[0].is_verified is True


def test_google_refuses_unverified_local_account(client, db_session, monkeypatch):
    client.post(
        "/api/auth/register",
        json={"full_name": "Pending", "email": "pending@example.com", "password": PASSWORD},
    )
    user = db_session.query(User).filter(User.email == "pending@example.com").one()
    assert user.is_verified is False

    enable_google(monkeypatch, identity(email="pending@example.com"))
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 409
    assert db_session.query(ExternalIdentity).count() == 0


def test_google_cannot_escalate_super_admin(client, db_session, monkeypatch):
    client.post(
        "/api/auth/register",
        json={"full_name": "Admin", "email": "admin@example.com", "password": PASSWORD},
    )
    user = db_session.query(User).filter(User.email == "admin@example.com").one()
    user.role = "super_admin"
    user.is_verified = False
    db_session.commit()
    original_id = user.id

    enable_google(monkeypatch, identity(email="admin@example.com"))
    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert response.status_code == 200

    db_session.expire_all()
    users = db_session.query(User).all()
    assert len(users) == 1
    assert users[0].id == original_id
    assert users[0].role == "super_admin"


def test_google_regular_user_is_not_admin(client, monkeypatch):
    enable_google(monkeypatch, identity())

    response = client.post("/api/auth/google", json={"id_token": "x" * 32})
    token = response.json()["access_token"]
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["role"] == "user"


def test_google_rejects_disabled_account(client, db_session, monkeypatch):
    enable_google(monkeypatch, identity(email="disabled@example.com"))
    first = client.post("/api/auth/google", json={"id_token": "x" * 32})
    assert first.status_code == 200

    user = db_session.query(User).filter(User.email == "disabled@example.com").one()
    user.is_active = False
    db_session.commit()

    second = client.post("/api/auth/google", json={"id_token": "y" * 32})
    assert second.status_code == 403


def test_code_exchange_requires_client_secret(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    with pytest.raises(GoogleAuthError):
        google_auth.exchange_google_code("code", REDIRECT_URI)


def test_authorization_url_enforces_redirect_allowlist(client, monkeypatch):
    enable_google(monkeypatch, identity())

    allowed = client.get(
        "/api/auth/google/authorization-url",
        params={"redirect_uri": REDIRECT_URI},
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["authorization_url"].startswith(settings.GOOGLE_AUTH_URI)
    assert f"client_id={CLIENT_ID}" in body["authorization_url"]
    assert "response_type=code" in body["authorization_url"]
    assert body["state"]

    denied = client.get(
        "/api/auth/google/authorization-url",
        params={"redirect_uri": "https://evil.example.com/callback"},
    )
    assert denied.status_code == 400


def test_callback_requires_valid_state(client, monkeypatch):
    enable_google(monkeypatch, identity())

    invalid = client.post(
        "/api/auth/google/callback",
        json={"code": "abc123", "redirect_uri": REDIRECT_URI, "state": "not-a-state"},
    )
    assert invalid.status_code == 400


def test_callback_exchanges_code_for_session(client, monkeypatch):
    enable_google(monkeypatch, identity())

    def fake_exchange(code, redirect_uri):
        return identity()

    monkeypatch.setattr(google_auth, "exchange_google_code", fake_exchange)

    state = google_auth.create_google_state()
    response = client.post(
        "/api/auth/google/callback",
        json={"code": "abc123", "redirect_uri": REDIRECT_URI, "state": state},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_verify_google_id_token_rejects_wrong_issuer(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        google_auth,
        "_verify_with_google",
        lambda id_token_value, audience: {
            "iss": "https://evil.example.com",
            "sub": "abc",
            "email": "user@example.com",
            "email_verified": True,
        },
    )
    with pytest.raises(GoogleAuthError):
        google_auth.verify_google_id_token("token")


def test_verify_google_id_token_requires_subject(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        google_auth,
        "_verify_with_google",
        lambda id_token_value, audience: {
            "iss": "accounts.google.com",
            "email": "user@example.com",
            "email_verified": True,
        },
    )
    with pytest.raises(GoogleAuthError):
        google_auth.verify_google_id_token("token")


def test_verify_google_id_token_normalizes_claims(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        google_auth,
        "_verify_with_google",
        lambda id_token_value, audience: {
            "iss": "https://accounts.google.com",
            "sub": "abc",
            "email": "USER@Example.com",
            "email_verified": "true",
        },
    )
    resolved = google_auth.verify_google_id_token("token")
    assert resolved.subject == "abc"
    assert resolved.email == "user@example.com"
    assert resolved.email_verified is True


def test_web_redirect_uri_from_frontend_url_allowed(client, monkeypatch):
    """The production web front-end redirects back to <FRONTEND_URL>/auth/google.

    The backend must allow that redirect URI automatically (derived from
    FRONTEND_URL) so the authorization-code flow is not rejected at the
    authorization-URL stage. Platform-specific schemes (e.g. ``frontend://``)
    are NOT derived from FRONTEND_URL and must still be supplied explicitly.
    """
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.test")
    enable_google(monkeypatch, identity())

    allowed = client.get(
        "/api/auth/google/authorization-url",
        params={"redirect_uri": "https://app.example.test/auth/google"},
    )
    assert allowed.status_code == 200
    assert "authorization_url" in allowed.json()

    denied = client.get(
        "/api/auth/google/authorization-url",
        params={"redirect_uri": "https://evil.example.com/auth/google"},
    )
    assert denied.status_code == 400


def test_mobile_custom_scheme_redirect_is_allowed(client, monkeypatch):
    """Native apps use the ``frontend://`` deep-link redirect URI.

    It must be supplied via GOOGLE_REDIRECT_URI / GOOGLE_ALLOWED_REDIRECT_URIS
    (it is never derived from FRONTEND_URL) and the backend must accept it.
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "frontend://auth/google")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:8081")

    response = client.get(
        "/api/auth/google/authorization-url",
        params={"redirect_uri": "frontend://auth/google"},
    )
    assert response.status_code == 200
    assert "authorization_url" in response.json()


def test_callback_returns_401_when_code_exchange_fails(client, monkeypatch):
    """A failing token exchange surfaces as a stable 401 + application code."""
    enable_google(monkeypatch, identity())
    monkeypatch.setattr(
        google_auth,
        "exchange_google_code",
        lambda code, redirect_uri: (_ for _ in ()).throw(
            GoogleAuthError("Unable to exchange the Google authorization code.")
        ),
    )

    state = google_auth.create_google_state()
    response = client.post(
        "/api/auth/google/callback",
        json={"code": "abc123", "redirect_uri": REDIRECT_URI, "state": state},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_GOOGLE_VERIFICATION_FAILED"

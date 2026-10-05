"""Tests for Admin tab visibility across both sign-in paths.

Reported problem
----------------
The Admin tab disappeared from the bottom tab bar. The tab is gated on the
signed-in user's role, and the gate is a *different* implementation from the
backend authorisation check: ``frontend/src/lib/roles.ts`` keeps its own set of
role strings, while the API authorises with
``app.routes.auth_dependency.require_admin``. Nothing asserted that the two
agree, so a tab can silently disappear while the account is in fact an admin,
and no test failed.

What is asserted here
---------------------
1. The role strings that reveal the tab are exactly the role strings the API
   accepts. This is the contract that broke.
2. A super administrator who signed in with email/password reaches a session
   whose ``/api/auth/me`` role reveals the tab.
3. The same is true when the super administrator signed in with Google, so the
   tab does not depend on which credential created the account.
4. A regular account never reveals the tab and is refused by the API, so the
   tab staying hidden is a real restriction rather than a cosmetic one.

No real credentials, tokens or secrets are asserted on, no production service is
contacted, and Google token verification is stubbed: every test runs against a
local SQLite database.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.bootstrap_super_admin import bootstrap
from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.routes import auth_dependency
from app.services import google_auth
from app.services.google_auth import GoogleIdentity

PASSWORD = "SecurePassword123!"
CLIENT_ID = "test-client.apps.googleusercontent.com"
ADMIN_EMAIL = "tab-admin@example.com"

ROLES_TS = (
    Path(__file__).resolve().parent.parent / "frontend" / "src" / "lib" / "roles.ts"
)


def frontend_admin_roles() -> set[str]:
    """Read the role strings the tab gate actually uses from the frontend.

    The file is parsed rather than duplicated so this test keeps tracking the
    real gate; a copy here would pass even after the tab logic changed.
    """
    source = ROLES_TS.read_text(encoding="utf-8")
    match = re.search(r"ADMIN_ROLES\s*=\s*new Set\(\[(.*?)\]\)", source, re.DOTALL)
    assert match, f"could not find ADMIN_ROLES in {ROLES_TS}"
    return set(re.findall(r"[\"']([^\"']+)[\"']", match.group(1)))


def backend_admin_roles() -> set[str]:
    """Derive the role strings the API accepts from the real dependency.

    ``require_admin`` is the authority, so the expected set is read from its
    behaviour instead of being restated from its source text.
    """
    allowed = set()
    for role in UserRole:
        user = User(id=1, full_name="Probe", email="probe@example.com", role=role.value)
        try:
            auth_dependency.require_admin(current_user=user)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            allowed.add(role.value)
    return allowed


def reveals_admin_tab(role: str | None) -> bool:
    """Mirror of ``isAdminRole`` using the roles parsed from the real file."""
    if not role:
        return False
    return role.strip().lower() in frontend_admin_roles()


@pytest.fixture(scope="function")
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_verified_admin(client, db_session, monkeypatch, email=ADMIN_EMAIL):
    """Register an account, verify it, then grant the super_admin role.

    Mirrors the documented provisioning order: the bootstrap refuses to act on
    an account that has not registered, so the tab cannot appear for an account
    that never completed email verification.
    """
    monkeypatch.setattr(settings, "BOOTSTRAP_SUPER_ADMIN_EMAIL", email)
    password = secrets.token_urlsafe(24)

    response = client.post(
        "/api/auth/register",
        json={"full_name": "Tab Admin", "email": email, "password": password},
    )
    assert response.status_code in (200, 201)

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    user.is_verified = True
    db_session.commit()

    bootstrap(db_session)
    db_session.refresh(user)
    assert user.role == "super_admin"
    return password


# --------------------------------------------------------------------------
# 1. The tab gate and the API gate must agree
# --------------------------------------------------------------------------


def test_tab_roles_match_the_roles_the_api_authorises():
    """The contract that broke when the tab disappeared.

    The frontend keeps its own list of role strings, and the API authorises from
    a different place. If the frontend list omits a role the API accepts, an
    administrator is refused by nothing and shown nothing.
    """
    assert frontend_admin_roles() == backend_admin_roles()


def test_every_backend_role_decides_the_tab_the_same_way():
    """No role may be authorised by the API but hidden from the tab, or the
    reverse, which would show a tab whose every request fails with 403."""
    for role in UserRole:
        allowed_by_api = role.value in backend_admin_roles()
        assert reveals_admin_tab(role.value) is allowed_by_api, role.value


# --------------------------------------------------------------------------
# 2. Email sign-in reveals the tab for a super administrator
# --------------------------------------------------------------------------


def test_email_super_admin_session_reveals_the_admin_tab(client, db_session, monkeypatch):
    password = register_verified_admin(client, db_session, monkeypatch)

    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": password},
    )
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200

    role = me.json()["role"]
    # This is the exact value `authService.storeUser` writes to `user_role`.
    assert reveals_admin_tab(role), f"role {role!r} would hide the Admin tab"

    # And the session really can use the surface the tab exposes.
    assert auth_dependency.require_admin(current_user=db_session.query(User).filter_by(
        email=ADMIN_EMAIL
    ).first())


# --------------------------------------------------------------------------
# 3. Google sign-in reveals the tab for the same super administrator
# --------------------------------------------------------------------------


def test_google_super_admin_session_reveals_the_admin_tab(client, db_session, monkeypatch):
    """The tab must depend on the account's role, not on how it was created.

    A super administrator who signed in with Google previously had no path to
    the Admin tab if the role was only ever granted through the email flow.
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "")
    monkeypatch.setattr(settings, "BOOTSTRAP_SUPER_ADMIN_EMAIL", ADMIN_EMAIL)

    def fake_verify(id_token_value, *, audience=None):
        return GoogleIdentity(
            subject="google-subject-admin",
            email=ADMIN_EMAIL,
            email_verified=True,
            name="Tab Admin",
            picture=None,
        )

    monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)

    signed_in = client.post(
        "/api/auth/google",
        json={"id_token": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(8)},
    )
    assert signed_in.status_code == 200, signed_in.text
    token = signed_in.json()["access_token"]

    # Promote the account the Google credential resolved to.
    user = db_session.query(User).filter(User.email == ADMIN_EMAIL).first()
    assert user is not None, "Google sign-in did not resolve to the expected account"
    user.is_verified = True
    db_session.commit()
    bootstrap(db_session)
    db_session.refresh(user)
    assert user.role == "super_admin"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert reveals_admin_tab(me.json()["role"]), "Google session would hide the Admin tab"


def test_google_regular_user_never_reveals_the_admin_tab(client, monkeypatch):
    """A Google account with no admin role must not reveal the tab."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "GOOGLE_ALLOWED_REDIRECT_URIS", "")

    def fake_verify(id_token_value, *, audience=None):
        return GoogleIdentity(
            subject="google-subject-regular",
            email="regular-google@example.com",
            email_verified=True,
            name="Regular Google",
            picture=None,
        )

    monkeypatch.setattr(google_auth, "verify_google_id_token", fake_verify)

    signed_in = client.post(
        "/api/auth/google",
        json={"id_token": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(8)},
    )
    assert signed_in.status_code == 200, signed_in.text

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {signed_in.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert not reveals_admin_tab(me.json()["role"])


# --------------------------------------------------------------------------
# 4. A hidden tab is a real restriction, not a cosmetic one
# --------------------------------------------------------------------------


def test_regular_user_is_refused_by_the_admin_api(client, db_session):
    """The API refuses the account, so hiding the tab is not the only defence."""
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Regular User",
            "email": "regular@example.com",
            "password": PASSWORD,
        },
    )
    user = db_session.query(User).filter(User.email == "regular@example.com").first()
    assert user is not None
    user.is_verified = True
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        json={"email": "regular@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert not reveals_admin_tab(me.json()["role"])

    with pytest.raises(HTTPException) as excinfo:
        auth_dependency.require_admin(current_user=user)
    assert excinfo.value.status_code == 403
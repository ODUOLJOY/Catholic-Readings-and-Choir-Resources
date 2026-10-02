import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import (
    generate_email_verification_token,
    issue_email_verification_token,
)

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


def register(client, email="verify@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Verify User", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response


def test_register_stores_only_token_hash(client, db_session):
    register(client)
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    assert user.is_verified is False
    assert user.email_verification_token
    assert len(user.email_verification_token) == 64


def test_verify_email_is_one_time(client, db_session):
    register(client)
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    token = issue_email_verification_token(db_session, user)

    first = client.post("/api/auth/verify-email", params={"token": token})
    assert first.status_code == 200

    db_session.expire_all()
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    assert user.is_verified is True
    assert user.email_verification_token is None

    second = client.post("/api/auth/verify-email", params={"token": token})
    assert second.status_code == 400


def test_verify_email_rejects_unissued_token(client, db_session):
    register(client)
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    forged = generate_email_verification_token(user)
    response = client.post("/api/auth/verify-email", params={"token": forged})
    assert response.status_code == 400


def test_resend_requires_email_delivery(client, monkeypatch):
    import app.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: False)
    response = client.post(
        "/api/auth/resend-verification", json={"email": "verify@example.com"}
    )
    assert response.status_code == 503


def test_resend_sends_for_unverified_account(client, db_session, monkeypatch):
    import app.routes.auth as auth_routes

    register(client)
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    original_hash = user.email_verification_token

    sent = {}

    def fake_send(recipient, token):
        sent["recipient"] = recipient
        sent["token"] = token

    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    monkeypatch.setattr(auth_routes, "send_email_verification_email", fake_send)

    response = client.post(
        "/api/auth/resend-verification", json={"email": "verify@example.com"}
    )
    assert response.status_code == 200
    assert sent["recipient"] == "verify@example.com"
    assert sent["token"]

    db_session.expire_all()
    user = db_session.query(User).filter(User.email == "verify@example.com").one()
    assert user.email_verification_token != original_hash


def test_forgot_password_does_not_leak_account_existence(client, monkeypatch):
    import app.routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "email_delivery_configured", lambda: True)
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda r, t: None)

    known = client.post(
        "/api/auth/forgot-password", json={"email": "verify@example.com"}
    )
    unknown = client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json()

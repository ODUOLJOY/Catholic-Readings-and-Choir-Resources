import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.auth.security import hash_password
from app.bootstrap_super_admin import bootstrap
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


def test_register_and_duplicate_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "user"

    # Duplicate email rejection
    response_dup = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another User",
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response_dup.status_code == 400


def test_login_success_and_failure(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Login User",
            "email": "loginuser@example.com",
            "password": "SecurePassword123!",
        },
    )

    # Success
    response = client.post(
        "/api/auth/login",
        json={
            "email": "loginuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # Failure: wrong password
    response_fail = client.post(
        "/api/auth/login",
        json={
            "email": "loginuser@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert response_fail.status_code == 401


def test_change_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Pass User",
            "email": "passuser@example.com",
            "password": "OldPassword123!",
        },
    )

    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": "passuser@example.com",
            "password": "OldPassword123!",
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Change password
    change_resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewSecurePassword456!",
        },
    )
    assert change_resp.status_code == 200

    # Verify old password fails login
    fail_resp = client.post(
        "/api/auth/login",
        json={
            "email": "passuser@example.com",
            "password": "OldPassword123!",
        },
    )
    assert fail_resp.status_code == 401

    # Verify new password succeeds login
    success_resp = client.post(
        "/api/auth/login",
        json={
            "email": "passuser@example.com",
            "password": "NewSecurePassword456!",
        },
    )
    assert success_resp.status_code == 200


def test_super_admin_bootstrap_flow(client, db_session):
    admin_email = "parmenasoduol1318@gmail.com"
    settings.BOOTSTRAP_SUPER_ADMIN_EMAIL = admin_email

    # Register user with super admin email
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Parmenas Oduol",
            "email": admin_email,
            "password": "AdminPassword123!",
        },
    )

    # Verify email in db manually for bootstrap requirement
    user = db_session.query(User).filter(User.email == admin_email).first()
    user.is_verified = True
    db_session.commit()

    # Run bootstrap
    bootstrap(db_session)

    db_session.refresh(user)
    assert user.role == "super_admin"

    # Login and check token contains super_admin role
    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": admin_email,
            "password": "AdminPassword123!",
        },
    )
    assert login_resp.status_code == 200
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "super_admin"

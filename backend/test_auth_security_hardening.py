import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
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


def register(client, email="hardening@example.com"):
    client.post(
        "/api/auth/register",
        json={"full_name": "Hardening User", "email": email, "password": PASSWORD},
    )


def test_malformed_subject_is_rejected(client):
    token = create_access_token(data={"sub": "not-an-int", "role": "user"})
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_missing_subject_is_rejected(client):
    token = create_access_token(data={"role": "user"})
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_disabled_account_cannot_login(client, db_session):
    register(client)
    user = db_session.query(User).filter(User.email == "hardening@example.com").one()
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "hardening@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403

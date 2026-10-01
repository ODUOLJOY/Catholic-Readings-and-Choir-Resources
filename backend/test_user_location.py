import app.models.favorite
import app.models.liturgical
import app.models.locations
import app.models.parish
import app.models.parish_request
import app.models.payment
import app.models.readings
import app.models.report
import app.models.saint
import app.models.user
import app.models.choir
import app.models.download
import app.models.notification
import app.models.content
import app.models.community
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User
from app.models.payment import Payment
import hashlib
from app.schemas.user import UserAdminResponse
from app.services.auth_service import (
    generate_reset_token,
    reset_password,
    verify_password,
)
from app.routes.admin import change_role
from app.routes.auth import ForgotPasswordRequest, forgot_password
from app.services import mpesa
from app.services import email as email_service
from app.routes.user import LocationUpdateRequest, update_user_location


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_user_and_parish(db: Session) -> tuple[User, Parish, Deanery, Diocese]:
    diocese = Diocese(name="Test Diocese", code="test-diocese")
    db.add(diocese)
    db.flush()

    deanery = Deanery(
        name="Test Deanery",
        code="test-deanery",
        diocese_id=diocese.id,
    )
    db.add(deanery)
    db.flush()

    parish = Parish(
        name="Test Parish",
        code="test-parish",
        deanery_id=deanery.id,
        diocese_id=diocese.id,
    )
    user = User(
        full_name="Test User",
        email="test@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add_all([parish, user])
    db.commit()
    return user, parish, deanery, diocese


def test_update_location_validates_and_saves_hierarchy(db: Session):
    user, parish, deanery, diocese = create_user_and_parish(db)

    result = update_user_location(
        LocationUpdateRequest(
            parish_id=parish.id,
            deanery_id=deanery.id,
            diocese_id=diocese.id,
        ),
        db,
        user,
    )

    assert result.parish_id == parish.id
    assert result.profile_setup_completed is True


def test_update_location_rejects_mismatched_diocese(db: Session):
    user, parish, deanery, _ = create_user_and_parish(db)
    other_diocese = Diocese(name="Other Diocese", code="other-diocese")
    db.add(other_diocese)
    db.commit()

    with pytest.raises(HTTPException) as error:
        update_user_location(
            LocationUpdateRequest(
                parish_id=parish.id,
                deanery_id=deanery.id,
                diocese_id=other_diocese.id,
            ),
            db,
            user,
        )

    assert error.value.status_code == 400


def test_password_reset_updates_the_password_hash(db: Session):
    user = User(
        full_name="Reset User",
        email="reset@example.org",
        hashed_password="$2b$12$wIGyXH18nUUjHWztpFzEFOoKv0uJ3Efgzq6R2eH7Bh2a0l3vN0b2K",
    )
    db.add(user)
    db.commit()
    token = generate_reset_token(user)
    user.password_reset_token = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.commit()
    old_hash = user.hashed_password

    reset_password(db, token, "Updated-Password-123!")

    db.refresh(user)
    assert user.hashed_password != old_hash
    assert verify_password("Updated-Password-123!", user.hashed_password)
    assert not verify_password("old-password", user.hashed_password)
    assert user.password_reset_token is None
    with pytest.raises(HTTPException, match="already used"):
        reset_password(db, token, "Another-Password-123!")


def test_non_super_admin_cannot_change_user_role(db: Session):
    admin = User(
        full_name="Admin",
        email="admin@example.org",
        hashed_password="not-a-real-password-hash",
        role="admin",
    )
    target = User(
        full_name="Target",
        email="target@example.org",
        hashed_password="not-a-real-password-hash",
        role="user",
    )
    db.add_all([admin, target])
    db.commit()

    with pytest.raises(HTTPException) as error:
        change_role(
            user_id=target.id,
            role="super_admin",
            db=db,
            current_user=admin,
        )

    db.refresh(target)
    assert error.value.status_code == 403
    assert target.role == "user"


def test_admin_user_response_excludes_password_hash(db: Session):
    user = User(
        full_name="Safe Response",
        email="safe@example.org",
        hashed_password="must-not-be-serialized",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    response = UserAdminResponse.model_validate(user)

    assert response.email == user.email
    assert "hashed_password" not in response.model_dump()


def test_mpesa_callback_verifies_provider_status_and_is_idempotent(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = User(
        full_name="Paying User",
        email="paying@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add(user)
    db.flush()
    payment = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="pending",
        checkout_request_id="checkout-123",
    )
    db.add(payment)
    db.commit()

    monkeypatch.setattr(
        mpesa,
        "query_stk_status",
        lambda _: {"ResultCode": 0, "ResultDesc": "The service request is processed successfully."},
    )
    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "checkout-123",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 10},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                        {"Name": "MpesaReceiptNumber", "Value": "QWE123"},
                    ]
                },
            }
        }
    }

    mpesa.process_callback(db, callback)
    db.refresh(payment)
    expiry_after_first_callback = payment.subscription_expires_at

    assert payment.status == "completed"
    assert payment.mpesa_receipt_number == "QWE123"
    assert expiry_after_first_callback is not None

    mpesa.process_callback(db, callback)
    db.refresh(payment)
    assert payment.subscription_expires_at == expiry_after_first_callback


def test_mpesa_callback_does_not_grant_subscription_for_mismatched_amount(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = User(
        full_name="Invalid Payment",
        email="invalid-payment@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add(user)
    db.flush()
    payment = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="pending",
        checkout_request_id="checkout-invalid",
    )
    db.add(payment)
    db.commit()
    monkeypatch.setattr(mpesa, "query_stk_status", lambda _: {"ResultCode": 0})
    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "checkout-invalid",
                "ResultCode": 0,
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 1000},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                        {"Name": "MpesaReceiptNumber", "Value": "BAD123"},
                    ]
                },
            }
        }
    }

    with pytest.raises(ValueError, match="do not match"):
        mpesa.process_callback(db, callback)

    db.rollback()
    db.refresh(payment)
    assert payment.status == "pending"
    assert payment.subscription_expires_at is None


def test_password_reset_request_fails_closed_without_email_configuration(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "")

    with pytest.raises(HTTPException) as error:
        forgot_password(
            ForgotPasswordRequest(email="member@example.org"),
            db,
        )

    assert error.value.status_code == 503
    assert "not configured" in error.value.detail


def test_password_reset_email_contains_a_link_without_returning_token(
    monkeypatch: pytest.MonkeyPatch,
):
    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            sent["server"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def starttls(self, context):
            sent["tls"] = context

        def login(self, username: str, password: str):
            sent["credentials"] = (username, password)

        def send_message(self, message, from_addr: str, to_addrs: list[str]):
            sent["message"] = message
            sent["recipients"] = (from_addr, to_addrs)

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "mailer@example.test")
    monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "test-only")
    monkeypatch.setattr(email_service.settings, "EMAIL_FROM", "noreply@example.test")
    monkeypatch.setattr(email_service.settings, "FRONTEND_URL", "https://app.example.test")

    email_service.send_password_reset_email(
        "member@example.org",
        "opaque-token",
    )

    message = sent["message"]
    assert sent["recipients"] == ("noreply@example.test", ["member@example.org"])
    assert "https://app.example.test/reset-password?token=opaque-token" in message.get_content()

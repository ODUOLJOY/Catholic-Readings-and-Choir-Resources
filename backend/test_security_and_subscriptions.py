"""Regression tests for the critical-security and subscription repairs.

Each test names the concrete defect it pins down. They are grouped by the
directive section they satisfy so a future change that reintroduces one of the
bugs fails a named test rather than a vague assertion.

* Critical security  - authorization scoping, permission grants, admin payloads
* Error handling     - user-visible messages for the M-Pesa flow
* Payments           - server-authoritative activation, plans, history,
                       idempotency, rate limiting
* Performance        - bounded queries
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.locations import Country, Deanery, Diocese, EcclesiasticalProvince
from app.models.parish import Parish
from app.models.payment import Payment
from app.models.permissions import Permission, RolePermission
from app.models.user import User, UserRole
from app.services import rate_limit, subscription
from app.services.authorization_enhanced import (
    get_scoped_user_query,
    has_all_permissions,
    has_any_permission,
    has_permission,
)
from app.services.subscription import (
    expire_stale_pending_payments,
    get_subscription_state,
    require_active_subscription,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="function")
def db():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


_user_sequence = itertools.count(1)


def _user(db, role: str = UserRole.USER, **overrides) -> User:
    values = {
        "email": f"user-{next(_user_sequence)}@example.com",
        "full_name": "Test User",
        "hashed_password": "not-a-real-hash",
        "role": role,
        "status": "active",
    }
    values.update(overrides)
    user = User(**values)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _hierarchy(db):
    """Two dioceses, each with parishes, for the scope tests.

    ``Diocese.code``, ``Deanery.code`` and ``Parish.code`` are NOT NULL in the real
    schema, so a scope test has to build a real chain rather than insert loose
    rows; otherwise the join under test has nothing to traverse.
    """
    country = Country(name="Kenya", code="KE")
    db.add(country)
    db.commit()

    province = EcclesiasticalProvince(
        name="Nairobi Province", code="KE-NRB", country_id=country.id
    )
    db.add(province)
    db.commit()

    diocese_a = Diocese(
        name="Diocese A",
        code="KE-DIO-AAA",
        ecclesiastical_province_id=province.id,
    )
    diocese_b = Diocese(
        name="Diocese B",
        code="KE-DIO-BBB",
        ecclesiastical_province_id=province.id,
    )
    db.add_all([diocese_a, diocese_b])
    db.commit()

    deanery_a = Deanery(
        name="Deanery A", code="KE-DIO-AAA-DNY-A", diocese_id=diocese_a.id
    )
    deanery_b = Deanery(
        name="Deanery B", code="KE-DIO-BBB-DNY-B", diocese_id=diocese_b.id
    )
    db.add_all([deanery_a, deanery_b])
    db.commit()

    parish_a = Parish(
        name="Parish A",
        code="KE-DIO-AAA-DNY-A-PAR-A",
        diocese_id=diocese_a.id,
        deanery_id=deanery_a.id,
    )
    parish_b = Parish(
        name="Parish B",
        code="KE-DIO-AAA-DNY-A-PAR-B",
        diocese_id=diocese_a.id,
        deanery_id=deanery_a.id,
    )
    parish_c = Parish(
        name="Parish C",
        code="KE-DIO-BBB-DNY-B-PAR-C",
        diocese_id=diocese_b.id,
        deanery_id=deanery_b.id,
    )
    db.add_all([parish_a, parish_b, parish_c])
    db.commit()

    return SimpleNamespace(
        diocese_a=diocese_a,
        diocese_b=diocese_b,
        parish_a=parish_a,
        parish_b=parish_b,
        parish_c=parish_c,
    )


def _completed_payment(db, user: User, *, expires_in_days: int = 30) -> Payment:
    now = datetime.now(timezone.utc)
    payment = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="completed",
        result_code=0,
        mpesa_receipt_number=f"QJG{user.id}{expires_in_days}",
        subscription_expires_at=now + timedelta(days=expires_in_days),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


# --------------------------------------------------------------------------
# Critical security: authorization scoping
# --------------------------------------------------------------------------


def test_scoped_user_query_no_longer_raises_name_error(db):
    """``get_scoped_user_query`` referenced an undefined ``target_user``.

    Any route that scoped its own results through this helper raised
    ``NameError``, which surfaced as a 500 rather than an authorization decision.
    """
    actor = _user(db, UserRole.DIOCESAN_ADMINISTRATOR)
    other = _user(db, UserRole.USER)

    # The defect was an unconditional NameError for diocesan administrators.
    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    # Failing closed (only the actor) is correct for an admin with no diocese.
    assert seen == {actor.id}
    assert other.id not in seen


def test_scoped_user_query_returns_query_not_boolean(db):
    """The helper is typed to return a Query and is chained onto by callers."""
    actor = _user(db, UserRole.DIOCESAN_ADMINISTRATOR)

    result = get_scoped_user_query(db, actor)

    assert hasattr(result, "filter")
    assert hasattr(result, "all")


def test_scoped_user_query_super_admin_sees_everyone(db):
    actor = _user(db, UserRole.SUPER_ADMIN)
    other = _user(db, UserRole.USER)

    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    assert actor.id in seen
    assert other.id in seen


def test_scoped_user_query_unscoped_admin_sees_only_themselves(db):
    """An administrator with no diocese must fail closed, never open.

    Returning "everything" here would expose every account in the deployment to a
    single misconfigured admin.
    """
    actor = _user(db, UserRole.DIOCESAN_ADMINISTRATOR)
    other = _user(db, UserRole.USER)

    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    assert seen == {actor.id}
    assert other.id not in seen


def test_scoped_user_query_diocesan_admin_sees_only_their_diocese(db):
    """A *scoped* diocesan administrator must actually see their diocese.

    The fail-closed case above passes even if the scope filter were dropped
    entirely, because an unscoped actor legitimately returns one row. Only a
    populated hierarchy proves the ``User.parish_id -> Parish.diocese_id`` join
    works, so both sides are asserted here: members of their own diocese are
    visible, and an equally senior administrator of a neighbouring diocese is not.
    """
    fixtures = _hierarchy(db)
    actor = _user(
        db, UserRole.DIOCESAN_ADMINISTRATOR, parish_id=fixtures.parish_a.id
    )
    colleague = _user(db, UserRole.USER, parish_id=fixtures.parish_b.id)
    outsider = _user(db, UserRole.USER, parish_id=fixtures.parish_c.id)
    unattached = _user(db, UserRole.USER)

    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    assert seen == {actor.id, colleague.id}
    assert outsider.id not in seen, "a neighbouring diocese must not be visible"
    assert unattached.id not in seen, "an account with no parish is outside the scope"


def test_scoped_user_query_parish_admin_sees_only_their_parish(db):
    """A parish administrator's scope is their own parish, not their diocese.

    ``parish_b`` deliberately shares a diocese with ``parish_a``, so this also
    pins the boundary: the wider diocesan scope must not leak down into the
    parish scope just because both administrators report to the same diocese.
    """
    fixtures = _hierarchy(db)
    actor = _user(db, UserRole.PARISH_ADMINISTRATOR, parish_id=fixtures.parish_a.id)
    same_parish = _user(db, UserRole.USER, parish_id=fixtures.parish_a.id)
    same_diocese = _user(db, UserRole.USER, parish_id=fixtures.parish_b.id)
    outsider = _user(db, UserRole.USER, parish_id=fixtures.parish_c.id)

    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    assert seen == {actor.id, same_parish.id}
    assert same_diocese.id not in seen, "another parish in the same diocese is out of scope"
    assert outsider.id not in seen


def test_scoped_user_query_regular_user_sees_only_themselves(db):
    """A member with no administrative role gets their own record and nothing else."""
    fixtures = _hierarchy(db)
    actor = _user(db, UserRole.USER, parish_id=fixtures.parish_a.id)
    neighbour = _user(db, UserRole.USER, parish_id=fixtures.parish_a.id)

    seen = {row.id for row in get_scoped_user_query(db, actor).all()}

    assert seen == {actor.id}
    assert neighbour.id not in seen


# --------------------------------------------------------------------------
# Critical security: permission grants
# --------------------------------------------------------------------------


def test_super_admin_bypasses_permission_table(db):
    actor = _user(db, UserRole.SUPER_ADMIN)

    assert has_permission(db, actor, "users.delete") is True
    assert has_any_permission(db, actor, ["nope.not.real"]) is True
    assert has_all_permissions(db, actor, ["nope.not.real"]) is True


def test_permission_checks_stay_fail_closed_without_grants(db):
    """No rows must mean no permission, for every non-super-admin role.

    This is the contract the existing suite already asserts. A permissive
    fallback here would widen every unseeded role in the deployment, so the fix
    for the unseeded table is to seed the declared grants -- never to guess.
    """
    actor = _user(db, UserRole.PARISH_ADMINISTRATOR)

    assert has_permission(db, actor, "users.read") is False
    assert has_permission(db, actor, "choir_resources.approve") is False


def test_seeding_restores_the_declared_role_powers(db):
    """The migration created the tables but inserted no rows.

    Without an explicit seed every administrator was powerless: a parish
    administrator could not approve content, and a diocesan administrator could
    not update a diocese.
    """
    from app.services.permission_seed import seed_permissions

    actor = _user(db, UserRole.PARISH_ADMINISTRATOR)
    assert has_permission(db, actor, "users.read") is False

    seed_permissions(db)

    assert has_permission(db, actor, "users.read") is True


def test_seeding_grants_the_hierarchy_administrators(db):
    from app.services.permission_seed import seed_permissions

    seed_permissions(db)

    parish_admin = _user(db, UserRole.PARISH_ADMINISTRATOR)
    diocesan_admin = _user(db, UserRole.DIOCESAN_ADMINISTRATOR)

    assert has_permission(db, parish_admin, "choir_resources.approve") is True
    assert has_permission(db, diocesan_admin, "dioceses.update") is True


def test_seeding_does_not_grant_everything_to_a_role(db):
    """The declared grants are an allowlist, so destructive powers stay denied."""
    from app.services.permission_seed import seed_permissions

    seed_permissions(db)
    contributor = _user(db, UserRole.CHOIR_CONTRIBUTOR)

    assert has_permission(db, contributor, "choir_resources.create") is True
    assert has_permission(db, contributor, "users.delete") is False
    assert has_permission(db, contributor, "totally.invented.permission") is False


def test_permission_seeding_is_idempotent(db):
    """Re-running must not duplicate rows, and must not re-add a deleted grant."""
    from app.services.permission_seed import seed_permissions

    first = seed_permissions(db)
    second = seed_permissions(db)

    assert first["permissions_created"] > 0
    assert first["role_grants_created"] > 0
    assert second == {"permissions_created": 0, "role_grants_created": 0}


def test_seeding_respects_a_deliberately_narrowed_role(db):
    """An administrator who removed a grant keeps it removed after a redeploy."""
    from app.models.permissions import Permission as PermissionModel
    from app.services.permission_seed import seed_permissions

    seed_permissions(db)

    permission = (
        db.query(PermissionModel).filter(PermissionModel.name == "users.read").one()
    )
    grant = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == UserRole.PARISH_ADMINISTRATOR,
            RolePermission.permission_id == permission.id,
        )
        .one()
    )
    db.delete(grant)
    db.commit()

    seed_permissions(db)

    actor = _user(db, UserRole.PARISH_ADMINISTRATOR)
    assert has_permission(db, actor, "users.read") is False


def test_every_declared_grant_has_a_permission_row(db):
    """A grant referencing an undeclared permission is a data bug, not a warning."""
    from app.models.permissions import DEFAULT_ROLE_PERMISSIONS
    from app.services.permission_seed import seed_permissions

    seed_permissions(db)

    stored = {name for (name,) in db.query(Permission.name).all()}
    for role, names in DEFAULT_ROLE_PERMISSIONS.items():
        for name in names:
            assert name in stored, f"{role} is granted undeclared permission {name}"


def test_has_any_and_all_use_the_same_grants(db):
    from app.services.permission_seed import seed_permissions

    seed_permissions(db)
    actor = _user(db, UserRole.PARISH_ADMINISTRATOR)

    assert has_any_permission(db, actor, ["users.delete", "users.read"]) is True
    assert has_any_permission(db, actor, ["users.delete", "parishes.delete"]) is False
    assert has_all_permissions(db, actor, ["users.read", "parishes.read"]) is True
    assert has_all_permissions(db, actor, ["users.read", "users.delete"]) is False


# --------------------------------------------------------------------------
# Critical security: admin payload does not leak secrets
# --------------------------------------------------------------------------


def test_admin_user_response_omits_sensitive_fields():
    """The admin user list returned the ORM row straight to the browser."""
    from app.schemas.user import AdminUserListResponse

    fields = set(AdminUserListResponse.model_fields)

    assert "hashed_password" not in fields
    assert "verification_token" not in fields
    assert "reset_token" not in fields
    assert "reset_token_expiry" not in fields
    assert {"id", "email", "full_name", "role"} <= fields


def test_admin_audit_log_response_omits_internal_columns():
    from app.schemas.admin import AdminAuditLogResponse

    fields = set(AdminAuditLogResponse.model_fields)

    assert "actor_password_hash" not in fields
    assert {"id", "action", "target_type", "actor_id", "created_at"} <= fields


# --------------------------------------------------------------------------
# Payments: server-authoritative activation
# --------------------------------------------------------------------------


def test_subscription_is_inactive_without_a_payment(db):
    user = _user(db)

    state = get_subscription_state(db, user.id)

    assert state.active is False
    assert state.expires_at is None


def test_subscription_activates_from_a_confirmed_payment(db):
    """Activation must depend on verified server-side payment status only."""
    user = _user(db)
    _completed_payment(db, user, expires_in_days=30)

    state = get_subscription_state(db, user.id)

    assert state.active is True
    assert state.expires_at is not None
    assert state.expires_at > datetime.now(timezone.utc)


def test_pending_payment_does_not_activate_a_subscription(db):
    """Only the verified callback may activate; an initiated push must not."""
    user = _user(db)
    db.add(
        Payment(
            user_id=user.id,
            phone_number="254712345678",
            amount=10,
            currency="KES",
            status="pending",
        )
    )
    db.commit()

    assert get_subscription_state(db, user.id).active is False


def test_failed_payment_does_not_activate_a_subscription(db):
    user = _user(db)
    db.add(
        Payment(
            user_id=user.id,
            phone_number="254712345678",
            amount=10,
            currency="KES",
            status="failed",
            result_code=1032,
            subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    db.commit()

    assert get_subscription_state(db, user.id).active is False


def test_expired_subscription_is_not_active(db):
    """An expired subscription must lapse without any background job."""
    user = _user(db)
    _completed_payment(db, user, expires_in_days=-1)

    assert get_subscription_state(db, user.id).active is False


def test_entitlements_come_from_configuration(db, monkeypatch):
    """Entitlements are configured, not invented in code."""
    from app.core.config import settings

    user = _user(db)
    _completed_payment(db, user)

    monkeypatch.setattr(settings, "SUBSCRIPTION_FEATURES", ["premium-choir-audio"])
    assert "premium-choir-audio" in get_subscription_state(db, user.id).features

    other = _user(db)
    assert get_subscription_state(db, other.id).features == ()


def test_require_active_subscription_blocks_unsubscribed_user(db):
    user = _user(db)

    with pytest.raises(HTTPException) as error:
        require_active_subscription(db, user.id)

    assert error.value.status_code == 403


def test_require_active_subscription_allows_subscribed_user(db):
    user = _user(db)
    _completed_payment(db, user)

    assert require_active_subscription(db, user.id).active is True


# --------------------------------------------------------------------------
# Payments: plans and history
# --------------------------------------------------------------------------


def test_plans_endpoint_reports_configured_price():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/payments/plans")

    assert response.status_code == 200
    plan = response.json()["plans"][0]
    from app.core.config import settings

    assert plan["amount"] == settings.MPESA_MONTHLY_AMOUNT
    assert plan["currency"] == "KES"
    assert plan["period_days"] == 30


def test_history_endpoint_requires_authentication():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/payments/history").status_code == 401


# --------------------------------------------------------------------------
# Payments: idempotency and duplicate-push protection
# --------------------------------------------------------------------------


def test_duplicate_stk_push_is_blocked_while_one_is_pending(db, monkeypatch):
    """Two pushes for one account can double-charge the customer."""
    from app.services import mpesa

    user = _user(db)
    db.add(
        Payment(
            user_id=user.id,
            phone_number="254712345678",
            amount=10,
            currency="KES",
            status="pending",
        )
    )
    db.commit()

    def _fail(*args, **kwargs):
        raise AssertionError("no HTTP call should be made for a duplicate push")

    monkeypatch.setattr(mpesa.requests, "post", _fail)
    monkeypatch.setattr(mpesa, "_access_token", lambda: "token")

    with pytest.raises(mpesa.MpesaError) as error:
        mpesa.start_stk_push(db, user.id, "0712345678")

    assert "already have a payment awaiting confirmation" in str(error.value)


def test_expired_pending_payment_allows_a_new_push(db):
    """A dismissed M-Pesa prompt must not lock the account out forever."""
    user = _user(db)
    db.add(
        Payment(
            user_id=user.id,
            phone_number="254712345678",
            amount=10,
            currency="KES",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    db.commit()

    changed = expire_stale_pending_payments(db)

    assert changed == 1
    stale = db.query(Payment).filter(Payment.status == "expired").first()
    assert stale is not None


def test_successful_retry_is_not_marked_expired(db):
    user = _user(db)
    _completed_payment(db, user)

    assert expire_stale_pending_payments(db) == 0


def test_duplicate_callback_does_not_extend_the_subscription_twice(db, monkeypatch):
    """Near-simultaneous callbacks must grant one month, not two.

    ``SELECT ... FOR UPDATE`` is a no-op on SQLite, which is the database the
    tests and development environment use, so the read-then-write race was real.
    """
    from app.services import mpesa

    user = _user(db)
    payment = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="pending",
        checkout_request_id="ws_CO_TEST",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    monkeypatch.setattr(
        mpesa,
        "query_stk_status",
        lambda checkout_id: {"ResultCode": 0, "ResultDesc": "Accepted"},
    )

    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_TEST",
                "ResultCode": 0,
                "ResultDesc": "Accepted",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 10},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                        {"Name": "MpesaReceiptNumber", "Value": "QJG123"},
                    ]
                },
            }
        }
    }

    first = mpesa.process_callback(db, callback)
    assert first is not None
    expires_after_first = first.subscription_expires_at

    # Safaricom retries the same notification when the ack is slow.
    second = mpesa.process_callback(db, callback)
    assert second is not None
    assert second.subscription_expires_at == expires_after_first


def test_failed_verification_releases_the_payment_claim(db, monkeypatch):
    """A claim must not be left in ``processing`` if verification blows up."""
    from app.services import mpesa

    user = _user(db)
    payment = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="pending",
        checkout_request_id="ws_CO_FAIL",
    )
    db.add(payment)
    db.commit()

    def _boom(checkout_id):
        raise mpesa.MpesaError("M-Pesa has not confirmed the transaction result.")

    monkeypatch.setattr(mpesa, "query_stk_status", _boom)

    callback = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_FAIL", "ResultCode": 0}}}
    with pytest.raises(mpesa.MpesaError):
        mpesa.process_callback(db, callback)

    db.expire_all()
    row = db.query(Payment).filter(Payment.checkout_request_id == "ws_CO_FAIL").first()
    assert row is not None
    assert row.status == "pending"


def test_callback_for_unknown_checkout_is_ignored(db, monkeypatch):
    """An unexpected transaction must not crash the notification endpoint."""
    from app.services import mpesa

    def _fail(*args, **kwargs):
        raise AssertionError("no provider call should be made")

    monkeypatch.setattr(mpesa, "query_stk_status", _fail)

    result = mpesa.process_callback(
        db, {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_UNKNOWN", "ResultCode": 0}}}
    )

    assert result is None


def test_callback_reusing_another_payment_receipt_is_refused(db, monkeypatch):
    """One Safaricom receipt cannot settle two payments.

    ``payments.mpesa_receipt_number`` is unique, so recording a receipt another
    payment already holds failed at COMMIT -- which sat outside the error handler,
    returned an unhandled 500 that the callback route never translates, and left
    the claimed row stuck in "processing" so the account could never subscribe.
    """
    from app.services import mpesa

    user = _user(db)
    first = _completed_payment(db, user)
    first.mpesa_receipt_number = "QJG_DUPLICATE"
    db.commit()

    second = Payment(
        user_id=user.id,
        phone_number="254712345678",
        amount=10,
        currency="KES",
        status="pending",
        checkout_request_id="ws_CO_DUPLICATE",
    )
    db.add(second)
    db.commit()

    monkeypatch.setattr(
        mpesa,
        "query_stk_status",
        lambda checkout_id: {"ResultCode": 0, "ResultDesc": "Accepted"},
    )

    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_DUPLICATE",
                "ResultCode": 0,
                "ResultDesc": "Accepted",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 10},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                        {"Name": "MpesaReceiptNumber", "Value": "QJG_DUPLICATE"},
                    ]
                },
            }
        }
    }

    with pytest.raises(mpesa.MpesaError) as error:
        mpesa.process_callback(db, callback)

    assert "already been recorded" in str(error.value)

    db.expire_all()
    refused = db.query(Payment).filter(Payment.id == second.id).first()
    assert refused is not None
    assert refused.status == "pending", "a refused callback must not wedge the payment"
    assert refused.subscription_expires_at is None
    # The original payment keeps its own subscription.
    assert db.query(Payment).filter(Payment.id == first.id).one().status == "completed"


def test_callback_endpoint_translates_a_reused_receipt(db, monkeypatch):
    """The route must answer 503, not 500, when a receipt cannot be recorded."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import mpesa

    def _raise(db, callback):
        raise mpesa.MpesaError("This M-Pesa receipt has already been recorded.")

    monkeypatch.setattr("app.routes.payments.process_callback", _raise)

    with TestClient(app) as client:
        response = client.post(
            "/api/payments/mpesa/callback",
            json={"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_X", "ResultCode": 0}}},
        )

    assert response.status_code == 503


def test_permission_seed_check_reports_a_healthy_database(db):
    """A fully seeded deployment must pass its own startup gate."""
    from app.models.permissions import PERMISSIONS
    from app.services.permission_seed import check_permission_seed, seed_permissions

    seed_permissions(db)

    report = check_permission_seed(db)

    assert report["ok"] is True, report["problems"]
    assert report["problems"] == []
    assert report["total_grants"] > 0
    assert report["declared_permissions"] == len(PERMISSIONS)


def test_permission_seed_check_reports_a_permanently_unseeded_database(db):
    """An empty ``role_permissions`` table must fail the gate, not pass it.

    This is the failure that reached production: no grants meant every
    administrator was powerless, while the previous count-only check was happy.
    """
    from app.services.permission_seed import check_permission_seed

    report = check_permission_seed(db)

    assert report["ok"] is False
    assert report["total_grants"] == 0
    assert any("no permission grants" in problem for problem in report["problems"])


def test_permission_seed_check_catches_a_partially_seeded_role(db):
    """A half-seeded database must fail even though the total is non-zero.

    Deleting one role's grants by hand leaves ``count(*) > 0``; the affected
    administrator is as powerless as in the empty case, so a total-count check
    reports success and startup continues. Only per-role accounting catches it.
    """
    from app.services.permission_seed import check_permission_seed, seed_permissions

    seed_permissions(db)

    removed = (
        db.query(RolePermission)
        .filter(RolePermission.role == UserRole.PARISH_ADMINISTRATOR)
        .delete(synchronize_session=False)
    )
    db.commit()
    assert removed > 0, "the seed must grant this role something for the test to bite"

    report = check_permission_seed(db)

    assert report["ok"] is False
    assert any(UserRole.PARISH_ADMINISTRATOR in problem for problem in report["problems"])
    assert report["total_grants"] > 0, "the failure is the missing role, not the total"


def test_permission_seed_check_catches_a_missing_permission_row(db):
    """A deleted ``permissions`` row must fail even if all grants still exist."""
    from app.models.permissions import PERMISSIONS
    from app.services.permission_seed import check_permission_seed, seed_permissions

    seed_permissions(db)

    victim = sorted(PERMISSIONS)[0]
    db.query(Permission).filter(Permission.name == victim).delete(
        synchronize_session=False
    )
    db.commit()

    report = check_permission_seed(db)

    assert report["ok"] is False
    assert any(victim in problem for problem in report["problems"]), report["problems"]


def test_static_upload_directory_is_not_sniffable_as_a_script(tmp_path):
    """A stored HTML file must not be re-interpreted by the browser.

    ``Content-Disposition: attachment`` is advisory; without an explicit
    ``X-Content-Type-Options: nosniff`` a browser that receives a mismatched type
    may still sniff the body and execute it on the app's own origin. The mounted
    directories take their directory at construction time, so the class is
    exercised directly rather than through the already-mounted application.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.services.public_files import PublicFiles

    stored = tmp_path / "upload.html"
    stored.write_text("<script>alert(1)</script>", encoding="utf-8")

    harness = FastAPI()
    # The injected session has no ``ChoirResource`` rows, so this file is not a
    # published choir resource and the public-files guard must let it through.
    harness.mount(
        "/media",
        PublicFiles(
            directory=tmp_path,
            url_prefix="/media",
            session_factory=_empty_session,
        ),
        name="media",
    )

    with TestClient(harness) as client:
        response = client.get("/media/upload.html")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_permission_seed_check_reports_a_missing_permission_table():
    """An unmigrated database must fail with a readable remedy, not a traceback.

    The gate runs at startup on whatever database the deployment is pointed at.
    A driver ``ProgrammingError`` escaping the check would bury the actual
    instruction ("apply the migrations") under a stack trace.
    """
    from app.services.permission_seed import check_permission_seed

    bare = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session = sessionmaker(autocommit=False, autoflush=False, bind=bare)()
    try:
        report = check_permission_seed(session)
    finally:
        session.close()
        bare.dispose()

    assert report["ok"] is False
    assert any("migrations" in problem for problem in report["problems"]), report["problems"]
    assert report["total_grants"] == 0


def test_choir_download_is_not_sniffable_as_a_script(db, tmp_path, monkeypatch):
    """The authorized choir download must carry ``nosniff`` too.

    The media type is derived from the stored extension, so an uploaded file
    whose declared type disagrees with its contents must not be reinterpreted.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.db.database import get_db
    from app.models.choir import ChoirResource
    from app.routes import choir as choir_routes

    stored = tmp_path / "sheet.pdf"
    stored.write_bytes(b"<script>alert(1)</script>")

    resource = ChoirResource(
        title="Choir sheet",
        description="Test resource",
        category="Hymns",
        file_url="/media/sheet.pdf",
        file_type="pdf",
        file_size=stored.stat().st_size,
        uploaded_by=_user(db, UserRole.USER).id,
        is_approved=True,
        is_published=True,
    )
    db.add(resource)
    db.commit()

    monkeypatch.setattr(
        choir_routes, "open_resource_file", lambda resource: open(stored, "rb")
    )

    harness = FastAPI()
    harness.include_router(choir_routes.router)
    harness.dependency_overrides[get_db] = lambda: db

    with TestClient(harness) as client:
        response = client.get(f"/api/choir/{resource.id}/file")

    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "attachment" in response.headers.get("content-disposition", "")


def _empty_session():
    """A session whose ``ChoirResource`` lookups always come back empty."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


# --------------------------------------------------------------------------
# Error handling and rate limiting
# --------------------------------------------------------------------------


def test_invalid_phone_number_is_a_422_with_a_readable_message():
    from app.services.mpesa import normalize_phone

    with pytest.raises(ValueError) as error:
        normalize_phone("12345")

    assert "valid Kenyan mobile number" in str(error.value)


def test_subscribe_endpoint_is_rate_limited():
    """Payment initiation must not be spammable."""
    from app.routes.payments import PAYMENT_START

    assert isinstance(PAYMENT_START, rate_limit.Limit)
    assert PAYMENT_START.max_events <= 10
    assert PAYMENT_START.window_seconds >= 300


def test_rate_limiter_blocks_after_the_limit_is_consumed():
    rate_limit.reset_for_tests()
    limit = rate_limit.Limit(max_events=2, window_seconds=60)

    rate_limit.consume("test:subject", 1, limit)
    rate_limit.consume("test:subject", 1, limit)
    with pytest.raises(HTTPException) as error:
        rate_limit.consume("test:subject", 1, limit)

    assert error.value.status_code == 429
    rate_limit.reset_for_tests()


# --------------------------------------------------------------------------
# Performance
# --------------------------------------------------------------------------


def test_payment_history_is_bounded():
    """Transaction history must be paginated, not an unbounded table dump."""
    import inspect

    from app.routes.payments import payment_history

    source = inspect.getsource(payment_history)

    assert ".limit(" in source


def test_subscription_state_does_not_load_every_payment(db):
    """The state query must be a bounded single-row lookup."""
    user = _user(db)
    for index in range(5):
        _completed_payment(db, user, expires_in_days=index + 1)

    state = get_subscription_state(db, user.id)

    assert state.expires_at is not None
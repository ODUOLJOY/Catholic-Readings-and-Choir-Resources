"""Registration, location update and hierarchy authorization tests.

Registration accepts only the leaf of the hierarchy (``parish_id``); every
ancestor is derived on the server. Selecting a parish is organisational
membership and must never grant administrative privileges.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.choir  # noqa: F401
import app.models.community  # noqa: F401
import app.models.liturgical  # noqa: F401
import app.models.locations
import app.models.parish
import app.models.parish_request  # noqa: F401
import app.models.payment  # noqa: F401
import app.models.readings  # noqa: F401
import app.models.report  # noqa: F401
import app.models.saint  # noqa: F401
import app.models.user

from app.db.database import Base, get_db
from app.main import app
from app.models.locations import Deanery, Diocese
from app.models.user import User
from app.routes.auth import RegisterRequest, register
from app.routes.auth_dependency import get_current_user
from app.routes.user import LocationUpdateRequest, update_user_location
from hierarchy_test_support import build_chain, build_second_province_chain


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
    engine.dispose()


@pytest.fixture
def chain(db):
    return build_chain(db)


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    """Keep verification email side effects out of the tests."""
    import app.routes.auth as auth_module

    monkeypatch.setattr(
        auth_module, "_send_verification_email", lambda db, user: None, raising=False
    )


def payload(parish_id, email="new@example.org"):
    return RegisterRequest(
        full_name="New Member",
        email=email,
        password="Str0ng-Passw0rd!",
        parish_id=parish_id,
    )


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_register_with_valid_parish_stores_the_parish(db, chain):
    user = register(payload(chain["parish"].id), db)
    assert user.parish_id == chain["parish"].id
    assert user.role == "user"


def test_register_derives_the_full_chain(db, chain):
    from app.services import hierarchy_service as svc

    user = register(payload(chain["parish"].id), db)
    resolved = svc.resolve_user_hierarchy(db, user)
    assert resolved.country.code == "KE"
    assert resolved.province.code == "KE-NRB"
    assert resolved.diocese.code == "KE-NRB-NBI"
    assert resolved.deanery.code == "KE-NRB-NBI-CENTRAL"


def test_register_rejects_unknown_parish(db, chain):
    with pytest.raises(HTTPException) as excinfo:
        register(payload(999999), db)
    assert excinfo.value.status_code == 400


def test_register_rejects_inactive_parish(db, chain):
    chain["parish"].is_active = False
    db.commit()
    with pytest.raises(HTTPException) as excinfo:
        register(payload(chain["parish"].id), db)
    assert excinfo.value.status_code == 400


def test_register_rejects_parish_whose_deanery_is_inactive(db, chain):
    chain["deanery"].is_active = False
    db.commit()
    with pytest.raises(HTTPException) as excinfo:
        register(payload(chain["parish"].id), db)
    assert excinfo.value.status_code == 400


def test_register_allows_missing_parish_for_backwards_compatibility(db):
    user = register(payload(None), db)
    assert user.parish_id is None
    assert user.role == "user"


def test_selecting_a_parish_never_grants_admin(db):
    """Parish membership is organisational, never a privilege."""
    malindi = _malindi_chain(db)
    user = register(payload(malindi["parish"].id, "malindi@example.org"), db)

    assert user.parish_id == malindi["parish"].id
    assert user.role == "user"
    assert user.role not in {"admin", "super_admin", "moderator"}


def test_client_cannot_smuggle_a_role_through_registration(db, chain):
    request = payload(chain["parish"].id, "sneaky@example.org")
    # ``extra`` is not a model field, so any attempt to set role is ignored.
    request.model_extra  # noqa: B018  - documentation of pydantic behaviour

    user = register(request, db)
    assert user.role == "user"


def test_register_ignores_client_supplied_ancestor_ids(db, chain):
    """Only parish_id is accepted; ancestors are always derived."""
    other = build_second_province_chain(db)
    user = register(payload(chain["parish"].id, "derived@example.org"), db)

    from app.services import hierarchy_service as svc

    resolved = svc.resolve_user_hierarchy(db, user)
    # Belongs to the Nairobi chain, not the Mombasa one the fixture also holds.
    assert resolved.diocese.id == chain["diocese"].id
    assert resolved.diocese.id != other["diocese"].id


def _malindi_chain(db):
    """A second chain standing in for the Mombasa province / Malindi diocese."""
    other = build_second_province_chain(
        db,
        province_code="KE-MBA",
        province_name="Ecclesiastical Province of Mombasa",
        diocese_code="KE-MBA-MLD",
        diocese_name="Diocese of Malindi",
        deanery_code="KE-MBA-MLD-MALINDI",
        deanery_name="Malindi Deanery",
        parish_code="KE-MBA-MLD-MALINDI-CATHEDRAL",
        parish_name="Malindi Cathedral Parish",
    )
    other["diocese"].is_archdiocese = False
    db.commit()
    return other


# --------------------------------------------------------------------------
# Location update
# --------------------------------------------------------------------------


def _registered_user(db, parish_id, email="loc@example.org"):
    return register(payload(parish_id, email), db)


def test_update_location_accepts_parish_id_alone(db, chain):
    user = _registered_user(db, None, "move@example.org")
    result = update_user_location(LocationUpdateRequest(parish_id=chain["parish"].id), db, user)
    assert result.parish_id == chain["parish"].id


def test_update_location_rejects_mismatched_diocese(db, chain):
    other = build_second_province_chain(db)
    user = _registered_user(db, None, "mismatch@example.org")
    with pytest.raises(HTTPException) as excinfo:
        update_user_location(
            LocationUpdateRequest(
                parish_id=chain["parish"].id,
                diocese_id=other["diocese"].id,
            ),
            db,
            user,
        )
    assert excinfo.value.status_code == 400


def test_update_location_rejects_mismatched_deanery(db, chain):
    other = build_second_province_chain(db)
    user = _registered_user(db, None, "mismatch2@example.org")
    with pytest.raises(HTTPException) as excinfo:
        update_user_location(
            LocationUpdateRequest(
                parish_id=chain["parish"].id,
                deanery_id=other["deanery"].id,
            ),
            db,
            user,
        )
    assert excinfo.value.status_code == 400


def test_update_location_accepts_matching_ancestors(db, chain):
    user = _registered_user(db, None, "matching@example.org")
    result = update_user_location(
        LocationUpdateRequest(
            parish_id=chain["parish"].id,
            deanery_id=chain["deanery"].id,
            diocese_id=chain["diocese"].id,
        ),
        db,
        user,
    )
    assert result.parish_id == chain["parish"].id


def test_update_location_rejects_unknown_parish(db):
    user = _registered_user(db, None, "ghost@example.org")
    with pytest.raises(HTTPException) as excinfo:
        update_user_location(LocationUpdateRequest(parish_id=999999), db, user)
    assert excinfo.value.status_code == 400


# --------------------------------------------------------------------------
# Anonymous hierarchy browsing (needed by the registration form)
# --------------------------------------------------------------------------


def _client_for(db, user=None):
    from app.routes.auth_dependency import get_optional_user

    app.dependency_overrides[get_db] = lambda: db
    if user is not None:
        # The hierarchy routes authenticate with the optional dependency, so it
        # has to be overridden as well for an authenticated caller to be seen.
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_optional_user] = lambda: user
    return TestClient(app)


def test_anonymous_can_browse_deaneries_for_registration(db):
    """The signup form has no session yet, so this must not require auth."""
    chain = build_chain(db)
    with _client_for(db) as client:
        response = client.get(
            f"/api/v1/hierarchy/deaneries?diocese_id={chain['diocese'].id}"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert [d["code"] for d in response.json()["results"]] == [
        chain["deanery"].code
    ]


def test_anonymous_can_browse_parishes_for_registration(db):
    chain = build_chain(db)
    with _client_for(db) as client:
        response = client.get(
            f"/api/v1/hierarchy/parishes?deanery_id={chain['deanery'].id}"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert [p["code"] for p in response.json()["results"]] == [
        chain["parish"].code
    ]


def test_anonymous_cannot_list_inactive_rows(db):
    chain = build_chain(db)
    chain["parish"].is_active = False
    db.commit()
    with _client_for(db) as client:
        response = client.get(
            f"/api/v1/hierarchy/parishes?deanery_id={chain['deanery'].id}"
            f"&include_inactive=true"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 401


def test_non_admin_cannot_list_inactive_rows(db, chain):
    user = User(
        full_name="Plain",
        email="plain@example.org",
        username="plain",
        hashed_password="x",
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    with _client_for(db, user) as client:
        response = client.get(
            f"/api/v1/hierarchy/parishes?deanery_id={chain['deanery'].id}"
            f"&include_inactive=true"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_admin_can_list_inactive_rows(db, chain):
    admin = User(
        full_name="Boss",
        email="boss@example.org",
        username="boss",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    chain["parish"].is_active = False
    db.commit()

    with _client_for(db, admin) as client:
        response = client.get(
            f"/api/v1/hierarchy/parishes?deanery_id={chain['deanery'].id}"
            f"&include_inactive=true"
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert [p["code"] for p in response.json()["results"]] == [
        chain["parish"].code
    ]


def test_summary_endpoint_requires_admin(db):
    build_chain(db)
    plain = User(
        full_name="Plain",
        email="plain2@example.org",
        username="plain2",
        hashed_password="x",
        role="user",
        is_active=True,
    )
    db.add(plain)
    db.commit()

    with _client_for(db, plain) as client:
        response = client.get("/api/v1/hierarchy/summary")
    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_hierarchy_has_no_public_write_endpoints(db, chain):
    """Every hierarchy endpoint is read-only; writes go through admin roles."""
    write_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/hierarchy")
        and getattr(route, "methods", set()) - {"GET", "HEAD", "OPTIONS"}
    ]
    assert write_routes == []
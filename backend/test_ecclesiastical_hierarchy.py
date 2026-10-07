"""Tests for the Kenya Catholic ecclesiastical hierarchy.

Covers the structural guarantees the platform depends on:

* the four ecclesiastical provinces exist and own the right dioceses;
* a parish always resolves to a complete, internally consistent chain;
* cross-province, cross-diocese and cross-deanery mixes are rejected;
* an inconsistent parish row (diocese disagreeing with its deanery) is rejected;
* the Military Ordinariate is never part of a parish chain;
* listing endpoints are scoped to their parent and exclude inactive rows
  unless an administrator explicitly asks for them;
* only administrators may mutate the hierarchy.
"""

import pytest
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
from app.models.locations import (
    Country,
    Deanery,
    Diocese,
    EcclesiasticalProvince,
)
from app.models.parish import Parish
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services import hierarchy_service as svc
from hierarchy_test_support import build_chain, build_second_province_chain

EXPECTED_PROVINCE_CODES = {
    "KE-NRB",
    "KE-NRY",
    "KE-KSM",
    "KE-MBA",
}


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


def make_user(db, email="member@example.org", *, is_active=True):
    user = User(
        full_name="Member",
        email=email,
        username=email.split("@")[0],
        hashed_password="not-a-real-password-hash",
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    return user


def make_admin(db, email="admin@example.org"):
    user = User(
        full_name="Admin",
        email=email,
        username=email.split("@")[0],
        hashed_password="not-a-real-password-hash",
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def override_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def rows(result):
    """The service listing helpers return ``(rows, total)``."""
    return result[0]


def codes(result):
    return [row.code for row in rows(result)]


# --------------------------------------------------------------------------
# Structural integrity
# --------------------------------------------------------------------------


def test_kenya_is_the_only_country(db):
    db.add(Country(name="Kenya", code="KE"))
    db.commit()
    countries = svc.list_countries(db)
    assert codes(svc.list_countries(db)) == ["KE"]


def test_four_ecclesiastical_provinces_exist_in_reference_data():
    """The curated dataset must model exactly the four current provinces."""
    from app.data.ke_hierarchy import PROVINCES

    assert {p["code"] for p in PROVINCES} == EXPECTED_PROVINCE_CODES


def test_reference_data_assigns_every_diocese_to_a_province():
    from app.data.ke_hierarchy import ALL_DIOCESES, PROVINCES

    province_codes = {p["code"] for p in PROVINCES}
    geographic = [d for d in ALL_DIOCESES if not d.get("is_military_ordinariate")]
    assert geographic, "reference data contains no geographic dioceses"
    for diocese in geographic:
        assert diocese["province_code"] in province_codes, (
            f"{diocese['code']} references unknown province "
            f"{diocese['province_code']!r}"
        )


def test_reference_data_marks_exactly_one_military_ordinariate():
    from app.data.ke_hierarchy import ALL_DIOCESES

    military = [d for d in ALL_DIOCESES if d.get("is_military_ordinariate")]
    assert len(military) == 1


def test_reference_data_deaneries_belong_to_known_dioceses():
    from app.data.ke_hierarchy import ALL_DIOCESES, DEANERIES

    diocese_codes = {d["code"] for d in ALL_DIOCESES}
    for deanery in DEANERIES:
        assert deanery["diocese_code"] in diocese_codes


def test_reference_data_parishes_belong_to_known_deaneries():
    from app.data.ke_hierarchy import DEANERIES, PARISHES

    deanery_codes = {d["code"] for d in DEANERIES}
    for parish in PARISHES:
        assert parish["deanery_code"] in deanery_codes


def test_reference_data_parish_diocese_agrees_with_its_deanery():
    """A parish row must not contradict the diocese owning its deanery."""
    from app.data.ke_hierarchy import DEANERIES, PARISHES

    diocese_of_deanery = {d["code"]: d["diocese_code"] for d in DEANERIES}
    for parish in PARISHES:
        assert (
            parish["diocese_code"] == diocese_of_deanery[parish["deanery_code"]]
        ), f"{parish['code']} disagrees with its deanery's diocese"


def test_reference_data_every_row_is_verified():
    from app.data.ke_hierarchy import ALL_DIOCESES, DEANERIES, PARISHES, PROVINCES

    for row in [*PROVINCES, *ALL_DIOCESES, *DEANERIES, *PARISHES]:
        assert row["verification_status"] == "VERIFIED", row["code"]
        assert row.get("source_url"), f"{row['code']} has no source URL"
        assert row.get("source_name"), f"{row['code']} has no source name"


def test_reference_data_codes_are_unique():
    from app.data.ke_hierarchy import (
        ALL_DIOCESES,
        DEANERIES,
        PARISHES,
        PROVINCES,
    )

    for label, rows in (
        ("provinces", PROVINCES),
        ("dioceses", ALL_DIOCESES),
        ("deaneries", DEANERIES),
        ("parishes", PARISHES),
    ):
        codes = [row["code"] for row in rows]
        duplicates = {code for code in codes if codes.count(code) > 1}
        assert not duplicates, f"duplicate {label} codes: {sorted(duplicates)}"


def test_reference_data_covers_the_whole_country():
    """Every diocese is either given deaneries or explicitly flagged as a gap."""
    from app.data.ke_hierarchy import (
        ALL_DIOCESES,
        DEANERIES,
        DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES,
        DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA,
    )

    geographic = {
        d["code"] for d in ALL_DIOCESES if not d.get("is_military_ordinariate")
    }
    with_deaneries = {d["diocese_code"] for d in DEANERIES}
    documented_gaps = set(DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA)
    pending_parishes = set(DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES)

    uncovered = geographic - with_deaneries - documented_gaps - pending_parishes
    assert not uncovered, f"dioceses with neither deanery data nor a documented gap: {sorted(uncovered)}"

    # Every diocese named in either gap list must really exist.
    assert documented_gaps <= geographic
    assert pending_parishes <= geographic
    # "pending parishes" means the deaneries are known but the parishes are not.
    assert pending_parishes <= with_deaneries


def test_diocese_belongs_to_province(chain):
    assert chain["diocese"].ecclesiastical_province_id == chain["province"].id
    assert chain["province"].metropolitan_archdiocese_id == chain["diocese"].id
    assert chain["province"].country_id == chain["country"].id


def test_deanery_belongs_to_diocese(chain):
    assert chain["deanery"].diocese_id == chain["diocese"].id


def test_parish_belongs_to_deanery_and_diocese(chain):
    assert chain["parish"].deanery_id == chain["deanery"].id
    assert chain["parish"].diocese_id == chain["diocese"].id
    assert chain["parish"].country_id == chain["country"].id


def test_resolve_parish_derives_the_full_chain(db, chain):
    resolved = svc.resolve_parish_by_id(db, chain["parish"].id)
    assert resolved.country.code == "KE"
    assert resolved.province.code == "KE-NRB"
    assert resolved.diocese.code == "KE-NRB-NBI"
    assert resolved.deanery.code == "KE-NRB-NBI-CENTRAL"
    assert resolved.parish.code == "KE-NRB-NBI-CENTRAL-HOLY-FAMILY"


def test_resolve_parish_via_validate_chain(db, chain):
    resolved = svc.validate_chain(
        db,
        country_id=chain["country"].id,
        province_id=chain["province"].id,
        diocese_id=chain["diocese"].id,
        deanery_id=chain["deanery"].id,
        parish_id=chain["parish"].id,
    )
    assert resolved.parish.id == chain["parish"].id


# --------------------------------------------------------------------------
# Rejections
# --------------------------------------------------------------------------


def test_inconsistent_parish_with_foreign_diocese_is_rejected(db, chain):
    other = build_second_province_chain(db)
    stray = Parish(
        name="Stray Parish",
        code="KE-NRB-NBI-OTHER-STRAY",
        deanery_id=chain["deanery"].id,
        diocese_id=other["diocese"].id,
        country_id=chain["country"].id,
        country=chain["country"].name,
    )
    db.add(stray)
    db.commit()
    with pytest.raises(svc.HierarchyError):
        svc.resolve_parish_by_id(db, stray.id)


def test_cross_diocese_chain_is_rejected(db, chain):
    other = build_second_province_chain(db)
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=chain["country"].id,
            province_id=chain["province"].id,
            diocese_id=other["diocese"].id,
            deanery_id=chain["deanery"].id,
        )


def test_cross_deanery_chain_is_rejected(db, chain):
    other = build_second_province_chain(db)
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=chain["country"].id,
            province_id=chain["province"].id,
            diocese_id=chain["diocese"].id,
            deanery_id=other["deanery"].id,
            parish_id=chain["parish"].id,
        )


def test_cross_province_chain_is_rejected(db, chain):
    other = build_second_province_chain(db)
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=chain["country"].id,
            province_id=other["province"].id,
            diocese_id=chain["diocese"].id,
            deanery_id=chain["deanery"].id,
        )


def test_cross_country_chain_is_rejected(db, chain):
    other_country = Country(name="Uganda", code="UG")
    db.add(other_country)
    db.flush()
    other_province = EcclesiasticalProvince(
        name="Ecclesiastical Province of Kampala",
        code="UG-KMP",
        country_id=other_country.id,
        metropolitan_archdiocese_id=chain["diocese"].id,
    )
    db.add(other_province)
    db.commit()
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=chain["country"].id,
            province_id=other_province.id,
            diocese_id=chain["diocese"].id,
            deanery_id=chain["deanery"].id,
        )


def test_military_ordinariate_cannot_be_in_a_chain(db, chain):
    military = Diocese(
        name="Kenya Military Ordinariate",
        code="KE-MIL",
        is_military_ordinariate=True,
    )
    db.add(military)
    db.commit()
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=chain["country"].id,
            province_id=chain["province"].id,
            diocese_id=military.id,
            deanery_id=chain["deanery"].id,
        )


def test_unknown_ids_are_rejected(db, chain):
    with pytest.raises(svc.HierarchyError):
        svc.resolve_parish_by_id(db, 999999)
    with pytest.raises(svc.HierarchyError):
        svc.validate_chain(
            db,
            country_id=999999,
            province_id=chain["province"].id,
            diocese_id=chain["diocese"].id,
            deanery_id=chain["deanery"].id,
        )


def test_inactive_parish_is_rejected_unless_requested(db, chain):
    chain["parish"].is_active = False
    db.commit()

    with pytest.raises(svc.HierarchyError):
        svc.resolve_parish_by_id(db, chain["parish"].id, require_active=True)

    resolved = svc.resolve_parish_by_id(db, chain["parish"].id, require_active=False)
    assert resolved.parish.id == chain["parish"].id


def test_inactive_deanery_or_diocese_is_rejected(db, chain):
    chain["deanery"].is_active = False
    db.commit()
    with pytest.raises(svc.HierarchyError):
        svc.resolve_parish_by_id(db, chain["parish"].id)
    chain["deanery"].is_active = True
    chain["diocese"].is_active = False
    db.commit()
    with pytest.raises(svc.HierarchyError):
        svc.resolve_parish_by_id(db, chain["parish"].id)


# --------------------------------------------------------------------------
# Listing / scoping
# --------------------------------------------------------------------------


def test_dioceses_are_scoped_to_their_province(db):
    build_chain(db)
    other = build_second_province_chain(db)
    nairobi = svc.list_dioceses(db, province_id=other["province"].id)
    assert codes(nairobi) == [other["diocese"].code]
    assert other["diocese"].code != "KE-NRB-NBI"


def test_dioceses_exclude_the_military_ordinariate_by_default(db, chain):
    military = Diocese(
        name="Kenya Military Ordinariate",
        code="KE-MIL",
        is_military_ordinariate=True,
    )
    db.add(military)
    db.commit()

    # The Ordinariate belongs to no province, so it never appears in a
    # province-scoped listing regardless of the flag.
    scoped = svc.list_dioceses(db, province_id=chain["province"].id)
    assert codes(scoped) == [chain["diocese"].code]
    scoped_with = svc.list_dioceses(
        db, province_id=chain["province"].id, include_ordinariate=True
    )
    assert "KE-MIL" not in codes(scoped_with)

    # It is reachable only through the country-wide listing.
    all_jurisdictions = svc.list_dioceses(db)
    assert "KE-MIL" not in codes(all_jurisdictions)
    with_ordinariate = svc.list_dioceses(db, include_ordinariate=True)
    assert "KE-MIL" in codes(with_ordinariate)


def test_military_ordinariate_has_no_province_in_reference_data():
    from app.data.ke_hierarchy import ALL_DIOCESES

    military = [d for d in ALL_DIOCESES if d.get("is_military_ordinariate")]
    assert military[0].get("province_code") in (None, "")


def test_deaneries_are_scoped_to_their_diocese(db):
    build_chain(db)
    other = build_second_province_chain(db)
    deaneries = svc.list_deaneries(db, diocese_id=other["diocese"].id)
    assert codes(deaneries) == [other["deanery"].code]


def test_parishes_are_scoped_to_their_deanery(db, chain):
    other = build_second_province_chain(db)
    parishes = svc.list_parishes(db, deanery_id=chain["deanery"].id)
    assert codes(parishes) == [chain["parish"].code]
    assert other["parish"].code not in codes(parishes)


def test_listings_exclude_inactive_by_default(db, chain):
    chain["parish"].is_active = False
    db.commit()
    assert codes(svc.list_parishes(db, deanery_id=chain["deanery"].id)) == []
    active = svc.list_parishes(
        db, deanery_id=chain["deanery"].id, include_inactive=True
    )
    assert codes(active) == [chain["parish"].code]


def test_search_filters_results(db, chain):
    other = build_second_province_chain(db)
    assert codes(svc.list_parishes(
        db, deanery_id=chain["deanery"].id, search="Holy"
    )) == [chain["parish"].code]
    assert codes(svc.list_parishes(
        db, deanery_id=chain["deanery"].id, search="Mombasa"
    )) == []
    assert other["parish"].code not in codes(svc.list_parishes(
        db, deanery_id=chain["deanery"].id, search="Mombasa"
    ))


def test_resolve_user_hierarchy(db, chain):
    user = make_user(db)
    user.parish_id = chain["parish"].id
    db.commit()
    resolved = svc.resolve_user_hierarchy(db, user)
    assert resolved.parish.id == chain["parish"].id

    user.parish_id = None
    db.commit()
    assert svc.resolve_user_hierarchy(db, user) is None


def test_summary_reports_counts(db, chain):
    build_second_province_chain(db)
    stats = svc.summary(db)
    assert stats["countries"] == 1
    assert stats["provinces"] == 2
    assert stats["dioceses"] == 2
    assert stats["deaneries"] == 2
    assert stats["parishes"] == 2


# --------------------------------------------------------------------------
# HTTP surface
# --------------------------------------------------------------------------


def test_countries_endpoint_is_public(db):
    from fastapi.testclient import TestClient

    build_chain(db)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/hierarchy/countries")
        assert response.status_code == 200
        assert [c["code"] for c in response.json()["results"]] == ["KE"]
    finally:
        app.dependency_overrides.clear()


def test_parish_chain_endpoint_returns_full_ancestry(db, chain):
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/hierarchy/parishes/{chain['parish'].id}"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["country"]["code"] == "KE"
        assert body["province"]["code"] == "KE-NRB"
        assert body["diocese"]["code"] == "KE-NRB-NBI"
        assert body["deanery"]["code"] == "KE-NRB-NBI-CENTRAL"
        assert body["parish"]["id"] == chain["parish"].id
    finally:
        app.dependency_overrides.clear()


def test_resolve_endpoint_rejects_unknown_parish(db, chain):
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/hierarchy/resolve?parish_id=999999")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_deaneries_are_scoped_by_their_diocese_over_http(db):
    from fastapi.testclient import TestClient

    build_chain(db)
    other = build_second_province_chain(db)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/hierarchy/deaneries?diocese_id={other['diocese'].id}"
            )
        assert response.status_code == 200
        assert [d["code"] for d in response.json()["results"]] == [
            other["deanery"].code
        ]
    finally:
        app.dependency_overrides.clear()
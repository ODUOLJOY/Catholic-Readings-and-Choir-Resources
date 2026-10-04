"""End-to-end functional test of the Kenya Catholic hierarchy feature.

This exercises the real feature over HTTP against a database populated by the
real importer, using the real reference dataset:

    import -> browse the cascade -> register with a parish -> read the derived
    chain -> update the location -> check that privileges were not escalated

It is deliberately separate from the unit tests so that a failure here means the
feature is unusable, not merely that a helper misbehaves.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ENTITIES = ("countries", "provinces", "dioceses", "deaneries", "parishes")

# The entity name used by the importer is not always the physical table name.
TABLES = {
    "countries": "countries",
    "provinces": "ecclesiastical_provinces",
    "dioceses": "dioceses",
    "deaneries": "deaneries",
    "parishes": "parishes",
}

# What a full import of the current reference dataset produces.
EXPECTED = {
    "countries": 1,
    "provinces": 4,
    "dioceses": 28,
    "deaneries": 73,
    "parishes": 127,
}


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_app(tmp_path_factory):
    """A real database populated by the real importer, plus the real app."""
    db_path = tmp_path_factory.mktemp("hierarchy") / "hierarchy.db"
    engine = create_engine(f"sqlite:///{db_path}")

    from app.db.database import Base
    import app.main  # noqa: F401  registers every model

    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        from scripts.import_hierarchy import import_hierarchy

        report = import_hierarchy(session)

    from app.db.database import get_db
    from app.main import app

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield app, engine, report
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture(scope="module")
def client(live_app):
    app, _engine, _report = live_app
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Cascade helpers that always walk from the API, never from hard-coded ids
# --------------------------------------------------------------------------


def _results(payload):
    assert "results" in payload, payload
    return payload["results"]


def _country_id(client):
    countries = _results(client.get("/api/v1/hierarchy/countries").json())
    assert len(countries) == 1
    return countries[0]["id"]


def _province(client, code):
    provinces = _results(
        client.get(f"/api/v1/hierarchy/provinces?country_id={_country_id(client)}").json()
    )
    return next(p for p in provinces if p["code"] == code)


def _dioceses(client, province_id=None):
    url = "/api/v1/hierarchy/dioceses"
    if province_id is not None:
        url += f"?province_id={province_id}"
    return _results(client.get(url).json())


def _diocese(client, code):
    return next(d for d in _dioceses(client) if d["code"] == code)


def _deaneries(client, diocese_id):
    return _results(
        client.get(f"/api/v1/hierarchy/deaneries?diocese_id={diocese_id}").json()
    )


def _parish_page(client, deanery_id, limit=200):
    return client.get(
        f"/api/v1/hierarchy/parishes?deanery_id={deanery_id}&limit={limit}"
    ).json()


@pytest.fixture(scope="module")
def selectable(client):
    """The first (province, diocese, deanery, parish) that actually has data.

    Most dioceses in the dataset still await official parish lists, so a test
    that hard-codes a jurisdiction would be testing empty data. This walks the
    cascade and returns the first branch a real user could actually complete.
    """
    for province in _results(
        client.get(f"/api/v1/hierarchy/provinces?country_id={_country_id(client)}").json()
    ):
        for diocese in _dioceses(client, province["id"]):
            for deanery in _deaneries(client, diocese["id"]):
                page = _parish_page(client, deanery["id"])
                if page["total"]:
                    return {
                        "province": province,
                        "diocese": diocese,
                        "deanery": deanery,
                        "parish": page["results"][0],
                    }
    raise AssertionError("no selectable parish exists in the reference dataset")


def _register(client, email, parish_id=None):
    """Register + log in, returning the bearer headers."""
    body = {
        "full_name": "E2E Member",
        "email": email,
        "password": "Str0ng-Passw0rd!",
    }
    if parish_id is not None:
        body["parish_id"] = parish_id

    response = client.post("/api/auth/register", json=body)
    assert response.status_code in (200, 201), response.text

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Str0ng-Passw0rd!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------


def test_importer_populated_the_database(live_app):
    _app, engine, report = live_app

    with engine.connect() as conn:
        counts = {
            entity: conn.execute(
                text(f"SELECT COUNT(*) FROM {TABLES[entity]}")
            ).scalar_one()
            for entity in ENTITIES
        }

    assert counts == EXPECTED

    for entity in ENTITIES:
        assert report.counts[entity]["created"] == EXPECTED[entity], entity
        assert report.counts[entity]["skipped"] == 0, entity

    # ``updated`` is expected on a first import: provinces are created before
    # dioceses can be attached to them, so the linking passes that attach each
    # diocese to its province and each province to its metropolitan archdiocese
    # report genuine changes. The strict zero-write guarantee is asserted for
    # re-runs in test_import_is_idempotent.
    assert report.counts["provinces"]["updated"] == EXPECTED["provinces"]

    # Every geographic diocese is attached to its province, but the Military
    # Ordinariate deliberately keeps a NULL province, so it is not "updated".
    geographic = EXPECTED["dioceses"] - 1
    assert report.counts["dioceses"]["updated"] == geographic

    for entity in ("countries", "deaneries", "parishes"):
        assert report.counts[entity]["updated"] == 0, entity


def test_import_is_idempotent(live_app):
    """A second and third run must not write, reorder or duplicate anything."""
    _app, engine, _report = live_app
    from scripts.import_hierarchy import import_hierarchy

    for run in (2, 3):
        with Session(engine) as session:
            report = import_hierarchy(session)

        for entity in ENTITIES:
            assert report.counts[entity]["created"] == 0, f"run {run}: {entity}"
            assert report.counts[entity]["updated"] == 0, f"run {run}: {entity}"
            assert report.counts[entity]["skipped"] > 0, f"run {run}: {entity}"

    with engine.connect() as conn:
        for entity in ENTITIES:
            stored = conn.execute(
                text(f"SELECT COUNT(*) FROM {TABLES[entity]}")
            ).scalar_one()
            assert stored == EXPECTED[entity], entity


def test_no_orphan_or_inconsistent_rows_after_import(live_app):
    _app, engine, _report = live_app
    with engine.connect() as conn:
        orphan_deaneries = conn.execute(
            text(
                "SELECT COUNT(*) FROM deaneries d "
                "LEFT JOIN dioceses x ON x.id = d.diocese_id WHERE x.id IS NULL"
            )
        ).scalar_one()
        orphan_parishes = conn.execute(
            text(
                "SELECT COUNT(*) FROM parishes p "
                "LEFT JOIN deaneries d ON d.id = p.deanery_id WHERE d.id IS NULL"
            )
        ).scalar_one()
        inconsistent = conn.execute(
            text(
                "SELECT COUNT(*) FROM parishes p JOIN deaneries d ON d.id = p.deanery_id "
                "WHERE p.diocese_id <> d.diocese_id"
            )
        ).scalar_one()
        unassigned = conn.execute(
            text(
                "SELECT COUNT(*) FROM dioceses "
                "WHERE is_military_ordinariate = 0 AND ecclesiastical_province_id IS NULL"
            )
        ).scalar_one()

    assert orphan_deaneries == 0
    assert orphan_parishes == 0
    assert inconsistent == 0
    assert unassigned == 0


def test_every_jurisdiction_carries_provenance(live_app):
    _app, engine, _report = live_app
    with engine.connect() as conn:
        missing = conn.execute(
            text(
                "SELECT COUNT(*) FROM dioceses "
                "WHERE source_url IS NULL OR source_name IS NULL "
                "OR verification_status IS NULL"
            )
        ).scalar_one()
        bad_status = conn.execute(
            text(
                "SELECT COUNT(*) FROM dioceses WHERE verification_status NOT IN "
                "('VERIFIED','NEEDS_REVIEW','INCOMPLETE')"
            )
        ).scalar_one()
    assert missing == 0
    assert bad_status == 0


# --------------------------------------------------------------------------
# Browsing the cascade (anonymous, exactly as the sign-up form does)
# --------------------------------------------------------------------------


def test_full_anonymous_cascade(client, selectable):
    country_id = _country_id(client)
    province = selectable["province"]
    assert province["id"] == _province(client, province["code"])["id"]

    diocese = selectable["diocese"]
    listing = _dioceses(client, province["id"])
    assert diocese["id"] in [d["id"] for d in listing]

    deanery = selectable["deanery"]
    assert deanery["id"] in [d["id"] for d in _deaneries(client, diocese["id"])]

    parish = selectable["parish"]
    page = _parish_page(client, deanery["id"])
    assert parish["id"] in [p["id"] for p in page["results"]]

    chain = client.get(f"/api/v1/hierarchy/parishes/{parish['id']}").json()
    assert chain["country"]["id"] == country_id
    assert chain["province"]["id"] == province["id"]
    assert chain["diocese"]["id"] == diocese["id"]
    assert chain["deanery"]["id"] == deanery["id"]
    assert chain["parish"]["id"] == parish["id"]


def test_nairobi_publishes_all_127_parishes_across_its_deaneries(client):
    nairobi = _diocese(client, "KE-NRB-NBI")
    assert nairobi["is_archdiocese"] is True
    assert nairobi["deanery_count"] == 17  # the official Nairobi figure

    deaneries = _deaneries(client, nairobi["id"])
    assert len(deaneries) == 17

    total = sum(_parish_page(client, d["id"])["total"] for d in deaneries)
    assert total == 127

    # Deanery counts on each row must agree with the stored data.
    for deanery in deaneries:
        assert deanery["parish_count"] == _parish_page(client, deanery["id"])["total"]


def test_search_narrows_each_level(client):
    """Search must filter, not merely paginate."""
    everywhere = _dioceses(client)
    assert len(everywhere) == 27  # the Military Ordinariate has no province

    matches = _dioceses(client)
    filtered = client.get("/api/v1/hierarchy/dioceses?search=meru").json()
    assert [d["code"] for d in filtered["results"]] == ["KE-NRY-MER"]
    assert filtered["total"] == 1

    assert client.get("/api/v1/hierarchy/countries?search=zzzz").json()["total"] == 0

    province = _province(client, "KE-NRB")
    hit = client.get(
        f"/api/v1/hierarchy/deaneries?diocese_id={_diocese(client, 'KE-NRB-NBI')['id']}&search=central"
    ).json()
    assert hit["total"] >= 1
    assert all("central" in d["name"].lower() for d in hit["results"])


def test_pagination_is_stable_and_bounded(client):
    diocese = _diocese(client, "KE-NRB-NBI")
    first = client.get(f"/api/v1/hierarchy/deaneries?diocese_id={diocese['id']}&limit=5").json()
    assert first["limit"] == 5
    assert first["total"] == 17
    assert first["has_more"] is True

    second = client.get(
        f"/api/v1/hierarchy/deaneries?diocese_id={diocese['id']}&limit=5&offset=5"
    ).json()
    ids = {d["id"] for d in first["results"]}
    assert not ids & {d["id"] for d in second["results"]}


def test_military_ordinariate_is_separate_and_has_no_cascade(client):
    default_codes = [d["code"] for d in _dioceses(client)]
    assert "KE-MIL-ORD" not in default_codes

    included = client.get("/api/v1/hierarchy/dioceses?include_ordinariate=true").json()
    military = [d for d in included["results"] if d["is_military_ordinariate"]]
    assert len(military) == 1
    assert military[0]["code"] == "KE-MIL-ORD"
    assert military[0]["deanery_count"] == 0

    # It belongs to no province, so it cannot be reached through one.
    for province in _results(
        client.get(f"/api/v1/hierarchy/provinces?country_id={_country_id(client)}").json()
    ):
        codes = [d["code"] for d in _dioceses(client, province["id"])]
        assert "KE-MIL-ORD" not in codes

    assert _deaneries(client, military[0]["id"]) == []


def test_deanery_counts_agree_with_stored_data(client):
    """Published counts must be real, and gaps must stay empty rather than invented."""
    dioceses = _dioceses(client)
    assert len(dioceses) == 27  # the Military Ordinariate has no province

    total_deaneries = 0
    with_deaneries = 0
    with_parishes = 0
    for diocese in dioceses:
        deaneries = _deaneries(client, diocese["id"])
        total_deaneries += len(deaneries)
        assert diocese["deanery_count"] == len(deaneries), diocese["code"]

        if not deaneries:
            # No deanery data means no cascade below, never a placeholder row.
            continue

        with_deaneries += 1
        published = sum(_parish_page(client, d["id"])["total"] for d in deaneries)
        if published:
            with_parishes += 1
            for deanery in deaneries:
                assert deanery["parish_count"] == _parish_page(
                    client, deanery["id"]
                )["total"], deanery["code"]

    assert total_deaneries == 73
    # Eight dioceses publish deaneries today; only Nairobi publishes parishes.
    # The rest are an honest, documented data gap rather than invented rows.
    assert with_deaneries == 8
    assert with_parishes == 1


def test_unknown_parent_returns_404(client):
    assert client.get("/api/v1/hierarchy/deaneries?diocese_id=999999").status_code == 404
    assert (
        client.get("/api/v1/hierarchy/parishes?deanery_id=999999").status_code == 404
    )
    assert client.get("/api/v1/hierarchy/parishes/999999").status_code == 404


def test_resolve_endpoint_validates_a_selection(client, selectable):
    parish = selectable["parish"]
    ok = client.get(f"/api/v1/hierarchy/resolve?parish_id={parish['id']}")
    assert ok.status_code == 200
    assert ok.json()["parish"]["id"] == parish["id"]
    assert ok.json()["diocese"]["id"] == selectable["diocese"]["id"]

    bad = client.get("/api/v1/hierarchy/resolve?parish_id=999999")
    assert bad.status_code == 400
    assert "detail" in bad.json()


# --------------------------------------------------------------------------
# Registration with a real parish
# --------------------------------------------------------------------------


def test_register_with_a_real_parish_derives_the_chain(client, selectable):
    parish = selectable["parish"]
    headers = _register(client, "e2e.register@example.org", parish["id"])

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "user"

    location = client.get("/api/v1/users/me/location", headers=headers).json()
    assert location == {
        "parish_id": parish["id"],
        "deanery_id": selectable["deanery"]["id"],
        "diocese_id": selectable["diocese"]["id"],
    }


def test_registration_without_a_parish_is_allowed(client):
    headers = _register(client, "e2e.nolocation@example.org")
    location = client.get("/api/v1/users/me/location", headers=headers).json()
    assert location == {"parish_id": None, "deanery_id": None, "diocese_id": None}


def test_registration_rejects_an_unknown_parish(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Ghost",
            "email": "e2e.ghost@example.org",
            "password": "Str0ng-Passw0rd!",
            "parish_id": 999999,
        },
    )
    assert response.status_code == 400


def test_registration_cannot_escalate_role(client, selectable):
    """A client-supplied role must be ignored entirely."""
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Aspiring Admin",
            "email": "e2e.escalate@example.org",
            "password": "Str0ng-Passw0rd!",
            "parish_id": selectable["parish"]["id"],
            "role": "admin",
        },
    )
    assert response.status_code in (200, 201), response.text

    login = client.post(
        "/api/auth/login",
        json={"email": "e2e.escalate@example.org", "password": "Str0ng-Passw0rd!"},
    )
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "user"


def test_registered_member_cannot_reach_admin_hierarchy(client, selectable):
    headers = _register(
        client, "e2e.privileges@example.org", selectable["parish"]["id"]
    )

    assert client.get("/api/v1/hierarchy/summary", headers=headers).status_code == 403

    response = client.get(
        f"/api/v1/hierarchy/parishes?deanery_id={selectable['deanery']['id']}"
        "&include_inactive=true",
        headers=headers,
    )
    assert response.status_code == 403


def test_anonymous_cannot_see_inactive_rows(client, selectable):
    response = client.get(
        f"/api/v1/hierarchy/parishes?deanery_id={selectable['deanery']['id']}"
        "&include_inactive=true"
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Moving a member between parishes
# --------------------------------------------------------------------------


def test_member_can_move_to_another_parish(client, selectable):
    """The update takes only parish_id; the server derives the ancestors."""
    headers = _register(client, "e2e.move@example.org")

    target = selectable["parish"]
    response = client.put(
        "/api/v1/users/me/location",
        json={"parish_id": target["id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    # The response is the updated user, and setup is now complete.
    assert response.json()["profile_setup_completed"] is True

    stored = client.get("/api/v1/users/me/location", headers=headers).json()
    assert stored["parish_id"] == target["id"]
    assert stored["deanery_id"] == selectable["deanery"]["id"]
    assert stored["diocese_id"] == selectable["diocese"]["id"]


def test_location_update_rejects_a_foreign_diocese(client, selectable):
    """A client cannot pair one parish with a different jurisdiction."""
    headers = _register(client, "e2e.mismatch@example.org")

    other = next(
        d
        for d in _dioceses(client)
        if d["id"] != selectable["diocese"]["id"]
    )
    response = client.put(
        "/api/v1/users/me/location",
        json={
            "parish_id": selectable["parish"]["id"],
            "diocese_id": other["id"],
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "diocese" in response.json()["detail"].lower()


def test_location_update_rejects_a_foreign_deanery(client, selectable):
    headers = _register(client, "e2e.deanerymismatch@example.org")

    other_deanery = next(
        d
        for d in _deaneries(client, selectable["diocese"]["id"])
        if d["id"] != selectable["deanery"]["id"]
    )
    response = client.put(
        "/api/v1/users/me/location",
        json={
            "parish_id": selectable["parish"]["id"],
            "deanery_id": other_deanery["id"],
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "deanery" in response.json()["detail"].lower()


def test_location_update_requires_authentication(client, selectable):
    response = client.put(
        "/api/v1/users/me/location",
        json={"parish_id": selectable["parish"]["id"]},
    )
    assert response.status_code in (401, 403)


def test_location_update_rejects_an_unknown_parish(client):
    headers = _register(client, "e2e.badmove@example.org")
    response = client.put(
        "/api/v1/users/me/location",
        json={"parish_id": 999999},
        headers=headers,
    )
    assert response.status_code == 400


def test_moving_user_records_a_parish_membership(client, selectable):
    """The move must be traceable, not silently overwrite the pointer."""
    headers = _register(client, "e2e.membership@example.org")
    response = client.put(
        "/api/v1/users/me/location",
        json={"parish_id": selectable["parish"]["id"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["parish_membership_status"] == "pending"

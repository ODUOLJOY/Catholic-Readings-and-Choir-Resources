"""Compatibility and lifecycle tests for the legacy locations API.

The hierarchy migration replaced ad-hoc jurisdiction codes with stable ``KE-*``
codes and uppercase verification statuses. Older admin tooling and payloads
still speak the old dialect, so these tests pin the translation behaviour:

* legacy codes and legacy display names resolve to the current diocese
* an unknown or ambiguous identifier resolves to nothing rather than guessing
* the admin statistics report real numbers
* deleting a parish deactivates it instead of destroying history
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User
from app.services import hierarchy_service


@pytest.fixture(scope="module")
def wired_app(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("locations") / "locations.db"
    engine = create_engine(f"sqlite:///{db_path}")

    from app.db.database import Base
    import app.main  # noqa: F401

    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        from scripts.import_hierarchy import import_hierarchy

        import_hierarchy(session)

    from app.db.database import get_db
    from app.main import app

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        # An administrator is needed for every mutating endpoint here.
        with Session(engine) as session:
            admin = User(
                email="locations.admin@example.org",
                hashed_password="x",
                full_name="Locations Admin",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            admin_headers = {"Authorization": f"Bearer {_token(admin)}"}

        yield client, engine, admin_headers


def _token(user):
    """Mint a real access token for a directly-created user."""
    from app.auth.security import create_access_token

    return create_access_token({"sub": str(user.id)})


# --------------------------------------------------------------------------
# Legacy identifier resolution
# --------------------------------------------------------------------------


def test_legacy_codes_are_not_stored_as_codes_anymore(wired_app):
    """Legacy codes must not linger alongside the stable KE-* codes."""
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        stored = session.execute(
            text("SELECT COUNT(*) FROM dioceses WHERE code = 'arch_nbo'")
        ).scalar_one()
    assert stored == 0


def test_legacy_display_name_resolves_to_current_diocese(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        found = hierarchy_service.resolve_legacy_diocese(
            session, "Archdiocese of Nairobi"
        )
        assert found is not None
        assert found.code == "KE-NRB-NBI"


def test_legacy_names_resolve_regardless_of_case_and_prefix(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        expected = "KE-NRY-MER"
        for label in (
            "Diocese of Meru",
            "diocese of meru",
            "MERU",
            "The Diocese of Meru",
        ):
            found = hierarchy_service.resolve_legacy_diocese(session, label)
            assert found is not None, label
            assert found.code == expected, label


def test_military_ordinariate_resolves_by_legacy_label(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        found = hierarchy_service.resolve_legacy_diocese(session, "Military Ordinariate")
        assert found is not None
        assert found.code == "KE-MIL-ORD"
        assert found.is_military_ordinariate is True


def test_current_code_still_resolves_exactly(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        found = hierarchy_service.resolve_legacy_diocese(session, "KE-NRB-NBI")
        assert found is not None
        assert found.code == "KE-NRB-NBI"


@pytest.mark.parametrize(
    "identifier",
    ["", "   ", "None", "Diocese of Atlantis", "KE-XXX-YYY"],
)
def test_unknown_identifiers_resolve_to_nothing(wired_app, identifier):
    """Unknown input must never be attached to an arbitrary diocese."""
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        assert hierarchy_service.resolve_legacy_diocese(session, identifier) is None


# --------------------------------------------------------------------------
# Explicit legacy mnemonic aliases
#
# Directory payloads produced before the hierarchy migration identify
# jurisdictions with mnemonics such as ``arch_nbo`` rather than stable codes.
# The resolver's docstring promises these resolve, so the mapping is pinned here.
# --------------------------------------------------------------------------


def test_legacy_mnemonics_resolve_to_their_canonical_codes(wired_app):
    _client, engine, _headers = wired_app
    expected = {
        "arch_nbo": "KE-NRB-NBI",
        "dio_kti": "KE-NRB-KTI",
        "mil_ord": "KE-MIL-ORD",
    }
    with Session(engine) as session:
        for mnemonic, code in expected.items():
            found = hierarchy_service.resolve_legacy_diocese(session, mnemonic)
            assert found is not None, mnemonic
            assert found.code == code, mnemonic


def test_legacy_mnemonics_resolve_regardless_of_case_and_padding(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        for identifier in ("arch_nbo", "ARCH_NBO", "  Arch_Nbo  "):
            found = hierarchy_service.resolve_legacy_diocese(session, identifier)
            assert found is not None, identifier
            assert found.code == "KE-NRB-NBI", identifier


def test_legacy_mnemonic_maps_to_the_military_ordinariate(wired_app):
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        found = hierarchy_service.resolve_legacy_diocese(session, "mil_ord")
        assert found is not None
        assert found.is_military_ordinariate is True
        # It has no province or deanery cascade.
        assert found.ecclesiastical_province_id is None


def test_alias_map_only_contains_evidence_backed_entries(wired_app):
    """Only mnemonics documented in this repository may be translated."""
    aliases = hierarchy_service.LEGACY_DIOCESE_CODE_ALIASES
    assert set(aliases) == {"arch_nbo", "dio_kti", "mil_ord"}

    _client, engine, _headers = wired_app
    with Session(engine) as session:
        existing = {row.code for row in session.query(Diocese).all()}
    # Every alias target must be a real diocese, or resolution would silently
    # fall through to a name match.
    assert set(aliases.values()) <= existing


@pytest.mark.parametrize(
    "identifier",
    ["dio_xxx", "arch_", "mil_", "dio_kti_typo", "unknown_mnemonic", "ke-nrb-nbi "],
)
def test_unknown_mnemonics_are_rejected(wired_app, identifier):
    """An unrecognised mnemonic must not fall back to an arbitrary diocese."""
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        assert hierarchy_service.resolve_legacy_diocese(session, identifier) is None


def test_malformed_identifiers_are_rejected(wired_app):
    _client, engine, _headers = wired_app
    malformed = ["---", "***", "../../etc/passwd", "arch_nbo'; DROP TABLE users;--"]
    with Session(engine) as session:
        for identifier in malformed:
            assert (
                hierarchy_service.resolve_legacy_diocese(session, identifier) is None
            ), identifier


def test_ambiguous_display_name_is_refused(wired_app):
    """Two dioceses sharing a normalised name must not resolve arbitrarily.

    ``Archdiocese of Nairobi`` and ``Diocese of Nairobi`` both normalise to
    ``nairobi``, so a name-only lookup matches two rows and must be refused.

    The fixture database is module-scoped, so the extra row is removed again to
    keep later count assertions intact.
    """
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        session.add(
            Diocese(
                name="Diocese of Nairobi",
                code="KE-AMB-001",
                ecclesiastical_province_id=1,
                is_active=True,
            )
        )
        session.commit()

        assert hierarchy_service.resolve_legacy_diocese(session, "Nairobi") is None
        assert (
            hierarchy_service.resolve_legacy_diocese(session, "Diocese of Nairobi")
            is None
        )
        # The explicit alias still resolves, because it is an exact code lookup.
        found = hierarchy_service.resolve_legacy_diocese(session, "arch_nbo")
        assert found is not None
        assert found.code == "KE-NRB-NBI"

        session.query(Diocese).filter(Diocese.code == "KE-AMB-001").delete()
        session.commit()

    # Cleanup must restore the unambiguous state.
    with Session(engine) as session:
        assert hierarchy_service.resolve_legacy_diocese(session, "Nairobi") is not None


def test_repeated_resolution_is_deterministic(wired_app):
    """Repeated imports must resolve to the same row every time."""
    _client, engine, _headers = wired_app
    with Session(engine) as session:
        first = hierarchy_service.resolve_legacy_diocese(session, "arch_nbo")
        ids = set()
        for _ in range(5):
            again = hierarchy_service.resolve_legacy_diocese(session, "arch_nbo")
            assert again is not None
            ids.add(again.id)
        assert first is not None
        assert ids == {first.id}


def test_legacy_bulk_import_with_mnemonics_imports(wired_app):
    """A payload keyed by the legacy mnemonics must import end to end.

    ``arch_nbo``, ``dio_kti`` and ``mil_ord`` are resolved through
    :data:`LEGACY_DIOCESE_CODE_ALIASES` rather than by name matching.
    """
    client, engine, headers = wired_app

    payload = {
        "dio_kti": {
            "name": "Diocese of Kitui",
            "deaneries": {
                "d_kti_alias_test": {
                    "name": "Alias Test Deanery",
                    "parishes": [
                        {"name": "Alias Test Parish", "code": "p_kti_alias_test"}
                    ],
                }
            },
        }
    }

    response = client.post("/api/v1/locations/import", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    results = response.json()

    assert results["jurisdictions_processed"] == 1
    assert results["errors"] == []
    assert results["parishes_added"] == 1

    with Session(engine) as session:
        parish = (
            session.query(Parish).filter(Parish.code == "p_kti_alias_test").one()
        )
        diocese = session.get(Diocese, parish.diocese_id)
        assert diocese.code == "KE-NRB-KTI"

        # The fixture database is module-scoped and later tests assert exact
        # counts, so the imported rows are removed again.
        deanery_id = parish.deanery_id
        session.delete(parish)
        session.commit()
        if deanery_id is not None:
            session.query(Deanery).filter(Deanery.id == deanery_id).delete()
            session.commit()


def test_bulk_import_reports_an_unknown_mnemonic(wired_app):
    """An unmapped mnemonic must be reported, never guessed.

    The payload name is deliberately non-existent too, so the mnemonic cannot be
    rescued by name matching.
    """
    client, _engine, headers = wired_app
    payload = {"dio_xyz": {"name": "Diocese of Atlantis", "deaneries": {}}}

    results = client.post(
        "/api/v1/locations/import", json=payload, headers=headers
    ).json()

    assert results["invalid_records"] == 1
    assert len(results["errors"]) == 1
    assert "dio_xyz" in results["errors"][0]


# --------------------------------------------------------------------------
# Admin statistics
# --------------------------------------------------------------------------


def test_admin_stats_report_real_counts(wired_app):
    client, _engine, headers = wired_app
    response = client.get("/api/v1/locations/admin/stats", headers=headers)
    assert response.status_code == 200
    stats = response.json()

    assert stats["total_jurisdictions"] == 28
    assert stats["military_ordinariate"] == 1
    assert stats["total_deaneries"] == 73
    assert stats["total_parishes"] == 127

    # The jurisdiction split must add up, which it never did when the types were
    # inferred from the old "arch_"/"dio_" code prefixes.
    assert (
        stats["archdioceses"] + stats["dioceses"] + stats["military_ordinariate"]
        == stats["total_jurisdictions"]
    )
    assert stats["archdioceses"] == 4  # Nairobi, Nyeri, Kisumu, Mombasa
    assert stats["dioceses"] == 23


def test_admin_stats_use_the_current_status_vocabulary(wired_app):
    client, _engine, headers = wired_app
    stats = client.get("/api/v1/locations/admin/stats", headers=headers).json()
    assert stats["verified_parishes"] == 127
    assert stats["needs_review_parishes"] == 0


def test_admin_stats_require_authentication(wired_app):
    client, _engine, _headers = wired_app
    assert client.get("/api/v1/locations/admin/stats").status_code in (401, 403)


# --------------------------------------------------------------------------
# Soft deletion lifecycle
# --------------------------------------------------------------------------


def test_deleting_a_parish_deactivates_it_and_keeps_history(wired_app):
    client, engine, headers = wired_app

    with Session(engine) as session:
        deanery = session.execute(
            text(
                "SELECT d.id FROM deaneries d JOIN dioceses x ON x.id = d.diocese_id "
                "WHERE x.code = 'KE-NRB-NBI' LIMIT 1"
            )
        ).scalar_one()
        parish = (
            session.query(Parish).filter(Parish.deanery_id == deanery).first()
        )
        parish_id, parish_name = parish.id, parish.name

    response = client.delete(f"/api/v1/locations/parishes/{parish_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # The row must still exist, carrying its history.
    with Session(engine) as session:
        stored = session.get(Parish, parish_id)
        assert stored is not None
        assert stored.name == parish_name
        assert stored.is_active is False


def test_deactivated_parish_disappears_from_the_default_cascade(wired_app):
    client, engine, headers = wired_app
    with Session(engine) as session:
        parish = (
            session.query(Parish)
            .filter(Parish.deanery_id.isnot(None), Parish.is_active.is_(True))
            .first()
        )
        parish_id, deanery_id = parish.id, parish.deanery_id

    client.delete(f"/api/v1/locations/parishes/{parish_id}", headers=headers)

    visible = client.get(f"/api/v1/hierarchy/parishes?deanery_id={deanery_id}").json()
    assert parish_id not in [p["id"] for p in visible["results"]]

    # It must still be resolvable by id for administrative and historical use.
    still_there = client.get(f"/api/v1/hierarchy/parishes/{parish_id}")
    assert still_there.status_code == 200


def test_a_deactivated_parish_cannot_be_selected_for_registration(wired_app):
    client, engine, headers = wired_app
    with Session(engine) as session:
        parish = (
            session.query(Parish).filter(Parish.deanery_id.isnot(None)).first()
        )
        parish_id = parish.id

    client.delete(f"/api/v1/locations/parishes/{parish_id}", headers=headers)

    assert client.get(f"/api/v1/hierarchy/resolve?parish_id={parish_id}").status_code == 400

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Too Late",
            "email": "locations.inactive@example.org",
            "password": "Str0ng-Passw0rd!",
            "parish_id": parish_id,
        },
    )
    assert response.status_code == 400


def test_a_restored_parish_can_be_selected_again(wired_app):
    client, engine, headers = wired_app
    with Session(engine) as session:
        parish = session.query(Parish).filter(Parish.deanery_id.isnot(None)).first()
        parish_id, deanery_id = parish.id, parish.deanery_id

    client.delete(f"/api/v1/locations/parishes/{parish_id}", headers=headers)
    assert client.get(f"/api/v1/hierarchy/resolve?parish_id={parish_id}").status_code == 400

    restored = client.post(
        f"/api/v1/locations/parishes/{parish_id}/restore", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert client.get(f"/api/v1/hierarchy/resolve?parish_id={parish_id}").status_code == 200

    visible = client.get(f"/api/v1/hierarchy/parishes?deanery_id={deanery_id}").json()
    assert parish_id in [p["id"] for p in visible["results"]]


def test_deleting_a_parish_requires_authentication(wired_app):
    client, engine, _headers = wired_app
    with Session(engine) as session:
        parish_id = session.query(Parish).first().id

    assert client.delete(f"/api/v1/locations/parishes/{parish_id}").status_code in (401, 403)
    assert (
        client.post(f"/api/v1/locations/parishes/{parish_id}/restore").status_code
        in (401, 403)
    )


def test_deleting_a_missing_parish_returns_404(wired_app):
    client, _engine, headers = wired_app
    assert (
        client.delete("/api/v1/locations/parishes/999999", headers=headers).status_code
        == 404
    )


# --------------------------------------------------------------------------
# Admin-created rows
# --------------------------------------------------------------------------


def test_admin_created_parish_uses_the_current_status_vocabulary(wired_app):
    client, engine, headers = wired_app
    with Session(engine) as session:
        deanery = session.query(Deanery).filter(Deanery.code != None).first()  # noqa: E711
        deanery_id, diocese_id = deanery.id, deanery.diocese_id

    response = client.post(
        "/api/v1/locations/parishes",
        params={
            "name": "Parish Under Review",
            "code": "p_test_review",
            "deanery_id": deanery_id,
            "diocese_id": diocese_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "NEEDS_REVIEW"

    with Session(engine) as session:
        stored = session.query(Parish).filter(Parish.code == "p_test_review").one()
        assert stored.verification_status == "NEEDS_REVIEW"
        stored_id = stored.id

    stats = client.get("/api/v1/locations/admin/stats", headers=headers).json()
    assert stats["needs_review_parishes"] == 1
    assert stats["total_parishes"] == 128

    client.delete(f"/api/v1/locations/parishes/{stored_id}", headers=headers)


def test_admin_cannot_pair_a_parish_with_a_foreign_diocese(wired_app):
    client, engine, headers = wired_app
    with Session(engine) as session:
        deanery = session.query(Deanery).first()
        other = (
            session.query(Diocese)
            .filter(Diocese.id != deanery.diocese_id)
            .first()
        )
        params = {
            "name": "Mismatched",
            "code": "p_test_mismatch",
            "deanery_id": deanery.id,
            "diocese_id": other.id,
        }

    response = client.post(
        "/api/v1/locations/parishes", params=params, headers=headers
    )
    assert response.status_code == 400


def test_admin_created_parish_requires_authentication(wired_app):
    client, engine, _headers = wired_app
    with Session(engine) as session:
        deanery = session.query(Deanery).first()
        params = {
            "name": "Anonymous",
            "code": "p_test_anon",
            "deanery_id": deanery.id,
            "diocese_id": deanery.diocese_id,
        }

    response = client.post("/api/v1/locations/parishes", params=params)
    assert response.status_code in (401, 403)


# --------------------------------------------------------------------------
# Legacy bulk import
# --------------------------------------------------------------------------


def test_legacy_bulk_import_payload_still_imports(wired_app):
    """A pre-migration payload must still land in the correct diocese."""
    client, engine, headers = wired_app

    payload = {
        "arch_nbo": {
            "name": "Archdiocese of Nairobi",
            "deaneries": {
                "d_nbo_legacy_test": {
                    "name": "Legacy Test Deanery",
                    "parishes": [
                        {"name": "Legacy Test Parish", "code": "p_nbo_legacy_test"}
                    ],
                }
            },
        }
    }

    response = client.post("/api/v1/locations/import", json=payload, headers=headers)
    assert response.status_code == 200
    results = response.json()

    assert results["jurisdictions_processed"] == 1
    assert results["errors"] == []
    assert results["deaneries_added"] == 1
    assert results["parishes_added"] == 1

    # The row must be attached to Nairobi, resolved through the legacy label.
    with Session(engine) as session:
        parish = session.query(Parish).filter(Parish.code == "p_nbo_legacy_test").one()
        diocese = session.get(Diocese, parish.diocese_id)
        assert diocese.code == "KE-NRB-NBI"
        assert parish.verification_status == "NEEDS_REVIEW"


def test_bulk_import_reports_an_unknown_jurisdiction(wired_app):
    client, _engine, headers = wired_app
    payload = {"dio_atlantis": {"name": "Diocese of Atlantis", "deaneries": {}}}

    results = client.post(
        "/api/v1/locations/import", json=payload, headers=headers
    ).json()

    assert results["invalid_records"] == 1
    assert len(results["errors"]) == 1
    assert "dio_atlantis" in results["errors"][0]


def test_bulk_import_requires_authentication(wired_app):
    client, _engine, _headers = wired_app
    assert client.post("/api/v1/locations/import", json={}).status_code in (401, 403)

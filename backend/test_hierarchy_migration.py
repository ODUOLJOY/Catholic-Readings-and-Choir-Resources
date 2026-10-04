"""Database migration checks for the ecclesiastical hierarchy migration.

Builds a database with the *legacy* hierarchy schema (before the country and
province tiers existed), applies migration ``20261002_07``, and asserts that:

* the new tables and columns appear;
* existing rows survive;
* ``parishes.name`` becomes unique per deanery instead of globally unique;
* ``parishes.deanery_id`` / ``diocese_id`` are backfilled and NOT NULL;
* legacy lowercase ``verification_status`` values are normalised;
* re-running the migration is safe.
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.db.database import Base
from app.models.locations import (
    Country,
    Deanery,
    Diocese,
    EcclesiasticalProvince,
)
from app.models.parish import Parish
from app.models.readings import Reading
from app.models.choir import ChoirResource
from app.models.user import User

MIGRATION_PATH = (
    Path(__file__).parent / "migrations" / "versions"
    / "20261002_07_ecclesiastical_hierarchy.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("hierarchy_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def legacy_engine(tmp_path):
    """A database holding the pre-migration hierarchy schema."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")

    metadata = sa.MetaData()
    # countries / ecclesiastical_provinces deliberately do NOT exist yet.
    sa.Table(
        "users", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parish_id", sa.Integer(), nullable=True),
    )
    sa.Table(
        "dioceses", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
    )
    sa.Table(
        "deaneries", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("diocese_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(50), nullable=False,
                  server_default="needs_review"),
    )
    sa.Table(
        "parishes", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        # The legacy schema made the parish name globally unique.
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("deanery_id", sa.Integer(), nullable=True),
        sa.Column("diocese_id", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("town", sa.String(120), nullable=True),
        sa.Column("county", sa.String(120), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(60), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo", sa.String(500), nullable=True),
        sa.Column("parish_priest", sa.String(120), nullable=True),
        sa.Column("assistant_priest", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(50), nullable=False,
                  server_default="needs_review"),
    )
    sa.Table(
        "readings", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reading_date", sa.String(50), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
    )
    sa.Table(
        "choir_resources", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO dioceses (id, name, code) VALUES (1, 'Archdiocese of Nairobi', 'arch_nbo')"
        ))
        conn.execute(sa.text(
            "INSERT INTO dioceses (id, name, code) VALUES (2, 'Diocese of Meru', 'dio_mer')"
        ))
        conn.execute(sa.text(
            "INSERT INTO deaneries (id, name, code, diocese_id, verification_status) "
            "VALUES (1, 'Nairobi Central Deanery', 'arch_nbo-central', 1, 'verified')"
        ))
        conn.execute(sa.text(
            "INSERT INTO parishes (id, name, code, deanery_id, diocese_id, country, "
            "verification_status) VALUES "
            "(1, 'St Mary Parish', 'KE-NBI-MARY', 1, NULL, 'Kenya', 'verified'),"
            "(2, 'St Joseph Parish', 'KE-NBI-JOSEPH', 1, 1, 'Kenya', 'needs_review')"
        ))
        conn.execute(sa.text(
            "INSERT INTO users (id, parish_id) VALUES (1, 1)"
        ))
    return engine


def _upgrade(engine):
    module = _load_migration()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        # Run the migration body with ``op`` bound to this connection.
        with Operations.context(context):
            module.upgrade()
    return module


def test_migration_creates_new_tables(legacy_engine):
    _upgrade(legacy_engine)
    inspector = sa.inspect(legacy_engine)
    tables = set(inspector.get_table_names())

    assert {"countries", "ecclesiastical_provinces"} <= tables

    province_columns = {c["name"] for c in inspector.get_columns("ecclesiastical_provinces")}
    assert {"country_id", "metropolitan_archdiocese_id", "short_name"} <= province_columns

    diocese_columns = {c["name"] for c in inspector.get_columns("dioceses")}
    assert {
        "ecclesiastical_province_id", "is_archdiocese", "is_military_ordinariate",
        "erected_on", "short_name", "is_active", "verification_status",
        "source_url", "source_name", "source_verified_at",
    } <= diocese_columns

    parish_columns = {c["name"] for c in inspector.get_columns("parishes")}
    assert {"country_id", "source_url", "verification_status"} <= parish_columns


def test_migration_preserves_existing_rows(legacy_engine):
    _upgrade(legacy_engine)
    with legacy_engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM dioceses")).scalar_one() == 2
        assert conn.execute(sa.text("SELECT COUNT(*) FROM deaneries")).scalar_one() == 1
        assert conn.execute(sa.text("SELECT COUNT(*) FROM parishes")).scalar_one() == 2
        assert conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one() == 1


def test_migration_backfills_parish_diocese_and_country(legacy_engine):
    _upgrade(legacy_engine)
    with legacy_engine.connect() as conn:
        # parish 1 had a NULL diocese_id and was backfilled from its deanery.
        assert conn.execute(
            sa.text("SELECT diocese_id FROM parishes WHERE id = 1")
        ).scalar_one() == 1
        # parish.country was NULL and is now Kenya.
        assert conn.execute(
            sa.text("SELECT country FROM parishes WHERE id = 1")
        ).scalar_one() == "Kenya"
        # country_id points at the seeded Kenya row.
        assert conn.execute(
            sa.text("SELECT countries.code FROM countries")
        ).scalar_one() == "KE"
        assert conn.execute(
            sa.text("SELECT country_id FROM parishes WHERE id = 1")
        ).scalar_one() is not None


def test_migration_normalises_legacy_verification_status(legacy_engine):
    _upgrade(legacy_engine)
    with legacy_engine.connect() as conn:
        statuses = {
            row[0] for row in conn.execute(sa.text("SELECT verification_status FROM parishes"))
        }
        assert statuses == {"VERIFIED", "NEEDS_REVIEW"}

        deanery_status = conn.execute(
            sa.text("SELECT verification_status FROM deaneries")
        ).scalar_one()
        assert deanery_status == "VERIFIED"


def test_migration_allows_same_parish_name_in_different_deaneries(legacy_engine):
    """The legacy global unique on parishes.name is relaxed to per-deanery."""
    _upgrade(legacy_engine)
    with legacy_engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO deaneries (id, name, code, diocese_id, verification_status) "
            "VALUES (2, 'Nairobi-Western Deanery', 'arch_nbo-western', 1, 'VERIFIED')"
        ))
        # Same display name as parish 1, but in a different deanery: must be
        # accepted now that uniqueness is scoped to the deanery.
        conn.execute(sa.text(
            "INSERT INTO parishes (id, name, code, deanery_id, diocese_id, "
            "verification_status) VALUES "
            "(3, 'St Mary Parish', 'KE-NBI-WESTERN-MARY', 2, 1, 'VERIFIED')"
        ))
    with legacy_engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM parishes")).scalar_one() == 3


def test_migration_rejects_duplicate_parish_name_within_one_deanery(legacy_engine):
    _upgrade(legacy_engine)
    with pytest.raises(Exception):
        with legacy_engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO parishes (id, name, code, deanery_id, diocese_id, "
                "verification_status) VALUES "
                "(99, 'St Mary Parish', 'KE-NBI-MARY-DUP', 1, 1, 'VERIFIED')"
            ))


def test_migration_enforces_not_null_on_parish_ancestors(legacy_engine):
    _upgrade(legacy_engine)
    inspector = sa.inspect(legacy_engine)
    parish_columns = {c["name"]: c for c in inspector.get_columns("parishes")}
    assert parish_columns["deanery_id"]["nullable"] is False
    assert parish_columns["diocese_id"]["nullable"] is False


def test_migration_is_safe_to_reapply(legacy_engine):
    _upgrade(legacy_engine)
    # A second application must not raise and must not lose data.
    _upgrade(legacy_engine)
    with legacy_engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM parishes")).scalar_one() == 2
        assert conn.execute(sa.text("SELECT COUNT(*) FROM dioceses")).scalar_one() == 2


def _downgrade(engine):
    module = _load_migration()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            module.downgrade()


def test_downgrade_then_upgrade_round_trip(legacy_engine):
    _upgrade(legacy_engine)
    _downgrade(legacy_engine)

    inspector = sa.inspect(legacy_engine)
    assert "countries" not in inspector.get_table_names()
    assert "ecclesiastical_provinces" not in inspector.get_table_names()

    # Rows must survive the round trip.
    with legacy_engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM parishes")).scalar_one() == 2
        assert conn.execute(sa.text("SELECT COUNT(*) FROM dioceses")).scalar_one() == 2
        assert conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one() == 1

    # Re-applying the upgrade restores the new tiers.
    _upgrade(legacy_engine)
    inspector = sa.inspect(legacy_engine)
    assert "countries" in inspector.get_table_names()
    assert conn_count(legacy_engine, "countries") == 1


def conn_count(engine, table):
    with engine.connect() as conn:
        return conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_downgrade_restores_legacy_lowercase_status(legacy_engine):
    _upgrade(legacy_engine)
    _downgrade(legacy_engine)
    with legacy_engine.connect() as conn:
        statuses = {
            row[0]
            for row in conn.execute(
                sa.text("SELECT verification_status FROM parishes")
            )
        }
        assert statuses == {"verified", "needs_review"}


def test_model_metadata_matches_migrated_schema(legacy_engine):
    """The ORM models and the migrated schema agree on the new columns."""
    _upgrade(legacy_engine)
    inspector = sa.inspect(legacy_engine)

    def model_columns(model):
        return {column.name for column in model.__table__.columns}

    for model, table in (
        (Country, "countries"),
        (EcclesiasticalProvince, "ecclesiastical_provinces"),
        (Diocese, "dioceses"),
        (Deanery, "deaneries"),
        (Parish, "parishes"),
    ):
        actual = {c["name"] for c in inspector.get_columns(table)}
        missing = model_columns(model) - actual
        assert not missing, f"{table} is missing columns: {sorted(missing)}"


def test_preflight_accepts_legacy_schema(legacy_engine):
    from app.services.migration_preflight import verify_legacy_schema

    with legacy_engine.connect() as conn:
        verify_legacy_schema(conn)
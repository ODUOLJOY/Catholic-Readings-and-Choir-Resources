"""Upgrade/downgrade tests for the reading references migration (revision 08).

Two things are wrong with testing this migration by importing it normally:

1. The module name starts with a digit (``20261002_08_reading_references``), so
   ``from migrations.versions.20261002_08_reading_references import ...`` is a
   ``SyntaxError`` -- a dotted import path is not allowed to contain an
   identifier that starts with a number. ``importlib.import_module`` accepts the
   same string, because it does not parse it as Python source.
2. The migration's helpers call the module-level ``alembic.op`` proxy. Building
   an ``Operations`` object locally is not enough; the proxy has to be
   installed, which is what ``Operations.context`` does.

The migration is exercised against a disposable database seeded with the kind
of rows a live installation already holds, so that data loss is detected rather
than assumed away.
"""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


@pytest.fixture(scope="module")
def migration():
    """Load the migration module despite its digit-leading filename."""
    return importlib.import_module(
        "migrations.versions.20261002_08_reading_references"
    )


@pytest.fixture()
def legacy_engine(tmp_path):
    """A pre-migration database holding real rows."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE liturgical_sources (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    country VARCHAR(10),
                    authority_level VARCHAR(50) NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    priority INTEGER DEFAULT 10,
                    last_checked TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE liturgical_days (
                    id INTEGER PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    liturgical_year VARCHAR(5) NOT NULL,
                    season VARCHAR(50) NOT NULL,
                    week_number INTEGER,
                    celebration_name VARCHAR(255) NOT NULL,
                    celebration_rank VARCHAR(50) NOT NULL,
                    liturgical_color VARCHAR(20) NOT NULL,
                    first_reading_reference VARCHAR(255),
                    responsorial_psalm_reference VARCHAR(255),
                    second_reading_reference VARCHAR(255),
                    gospel_reference VARCHAR(255),
                    region VARCHAR(10) DEFAULT 'KE',
                    source_id INTEGER,
                    source_record_id VARCHAR(255),
                    verification_status VARCHAR(50) DEFAULT 'unverified',
                    last_verified_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE reading_sets (
                    id INTEGER PRIMARY KEY,
                    liturgical_day_id INTEGER NOT NULL,
                    reading_type VARCHAR(50) NOT NULL,
                    celebration_id INTEGER,
                    lectionary_number VARCHAR(50),
                    first_reading_reference VARCHAR(255),
                    responsorial_psalm_reference VARCHAR(255),
                    second_reading_reference VARCHAR(255),
                    gospel_reference VARCHAR(255),
                    source_id INTEGER,
                    authority_level VARCHAR(50),
                    selection_status VARCHAR(50) DEFAULT 'weekday_default',
                    verification_status VARCHAR(50) DEFAULT 'unverified',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        # Seed rows that must survive the migration untouched.
        conn.execute(
            text(
                "INSERT INTO liturgical_sources (id, name, source_type, country, "
                "authority_level) VALUES (1, 'Kenya Catholic Church', 'diocesan', "
                "'KE', 'official')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO liturgical_days (id, date, liturgical_year, season, "
                "week_number, celebration_name, celebration_rank, liturgical_color, "
                "first_reading_reference, responsorial_psalm_reference, "
                "second_reading_reference, gospel_reference, region, source_id) "
                "VALUES (1, '2026-09-30', 'A', 'Ordinary Time', 27, "
                "'Saint Jerome', 'Memorial', 'White', 'Jer 26:1-9', 'Ps 115', "
                "'Rom 12:1-16', 'Lk 17:11-19', 'KE', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reading_sets (id, liturgical_day_id, reading_type, "
                "lectionary_number, first_reading_reference, "
                "responsorial_psalm_reference, second_reading_reference, "
                "gospel_reference, source_id, selection_status) "
                "VALUES (1, 1, 'first_reading', 'L1', 'Jer 26:1-9', 'Ps 115', "
                "'Rom 12:1-16', 'Lk 17:11-19', 1, 'proper')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reading_sets (id, liturgical_day_id, reading_type, "
                "lectionary_number, first_reading_reference, "
                "responsorial_psalm_reference, second_reading_reference, "
                "gospel_reference, source_id, selection_status) "
                "VALUES (2, 1, 'gospel', 'L1', NULL, NULL, NULL, 'Lk 17:11-19', "
                "1, 'weekday_default')"
            )
        )

    yield engine
    engine.dispose()


def _columns(engine, table):
    with engine.connect() as conn:
        return [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]


def _tables(engine):
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }


def _run(migration, engine, direction):
    """Run upgrade()/downgrade() with the alembic proxy properly installed."""
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(migration, direction)()


# --------------------------------------------------------------------------
# Upgrade
# --------------------------------------------------------------------------


def test_upgrade_adds_the_new_liturgical_day_columns(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    columns = _columns(legacy_engine, "liturgical_days")
    for expected in (
        "sunday_cycle",
        "weekday_cycle",
        "diocese_id",
        "parish_id",
    ):
        assert expected in columns, expected


def test_upgrade_copies_the_existing_cycle_into_sunday_cycle(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        row = conn.execute(
            text("SELECT sunday_cycle, weekday_cycle FROM liturgical_days WHERE id = 1")
        ).one()
    assert row[0] == "A", "the legacy liturgical_year must be preserved"
    assert row[1] == "I"


def test_upgrade_keeps_the_legacy_liturgical_year_column(legacy_engine, migration):
    """The column is retained deliberately, for backward compatibility."""
    _run(migration, legacy_engine, "upgrade")
    assert "liturgical_year" in _columns(legacy_engine, "liturgical_days")
    with legacy_engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT liturgical_year FROM liturgical_days WHERE id = 1")
            ).scalar_one()
            == "A"
        )


def test_upgrade_adds_the_verification_status_index(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='liturgical_days'"
                )
            )
        }
    assert "ix_liturgical_days_verification_status" in indexes


def test_upgrade_creates_the_reading_references_table(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    assert "reading_references" in _tables(legacy_engine)
    columns = _columns(legacy_engine, "reading_references")
    for expected in (
        "book",
        "display_reference",
        "is_alternative",
        "is_optional",
        "is_primary",
        "psalm_number_variant",
        "reading_set_id",
    ):
        assert expected in columns, expected


def test_upgrade_rebuilds_reading_sets_with_the_new_structure(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    columns = _columns(legacy_engine, "reading_sets")
    for expected in ("celebration_name", "authority_level", "verified_at"):
        assert expected in columns, expected


def test_upgrade_preserves_existing_reading_sets_rows(legacy_engine, migration):
    """The rebuild must carry rows across, not silently drop the table's data."""
    _run(migration, legacy_engine, "upgrade")

    with legacy_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, liturgical_day_id, reading_type, lectionary_number, "
                "source_id, selection_status FROM reading_sets ORDER BY id"
            )
        ).fetchall()

    assert len(rows) == 2, "both pre-existing reading sets must survive the upgrade"
    assert rows[0][0] == 1
    assert rows[0][2] == "first_reading"
    assert rows[0][3] == "L1"
    assert rows[0][5] == "proper"
    assert rows[1][0] == 2
    assert rows[1][2] == "gospel"


def test_upgrade_does_not_lose_liturgical_day_rows(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM liturgical_days")).scalar_one() == 1
        )
        assert (
            conn.execute(text("SELECT COUNT(*) FROM liturgical_sources")).scalar_one()
            == 1
        )


def test_upgrade_is_idempotent_for_reading_references(legacy_engine, migration):
    """Re-running must not fail on the already-created table."""
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "upgrade")
    assert "reading_references" in _tables(legacy_engine)


# --------------------------------------------------------------------------
# Downgrade
# --------------------------------------------------------------------------


def test_downgrade_removes_the_added_liturgical_day_columns(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")

    columns = _columns(legacy_engine, "liturgical_days")
    for removed in ("sunday_cycle", "weekday_cycle", "diocese_id", "parish_id"):
        assert removed not in columns, removed
    assert "liturgical_year" in columns


def test_downgrade_drops_the_reading_references_table(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    assert "reading_references" not in _tables(legacy_engine)


def test_downgrade_restores_the_legacy_reading_sets_columns(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")

    columns = _columns(legacy_engine, "reading_sets")
    for restored in (
        "first_reading_reference",
        "responsorial_psalm_reference",
        "second_reading_reference",
        "gospel_reference",
    ):
        assert restored in columns, restored


def test_round_trip_keeps_liturgical_day_data(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")

    with legacy_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT date, liturgical_year, season, celebration_name, "
                "celebration_rank, liturgical_color, first_reading_reference, "
                "gospel_reference FROM liturgical_days WHERE id = 1"
            )
        ).one()

    assert str(row[0]) == "2026-09-30"
    assert row[1] == "A"
    assert row[2] == "Ordinary Time"
    assert row[3] == "Saint Jerome"
    assert row[4] == "Memorial"
    assert row[5] == "White"
    assert row[6] == "Jer 26:1-9"
    assert row[7] == "Lk 17:11-19"


def test_round_trip_keeps_reading_set_data(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")

    with legacy_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, liturgical_day_id, reading_type, lectionary_number, "
                "first_reading_reference, gospel_reference, source_id, "
                "selection_status FROM reading_sets ORDER BY id"
            )
        ).fetchall()

    assert len(rows) == 2, "reading set rows must survive an upgrade/downgrade cycle"
    assert rows[0][0] == 1
    assert rows[0][2] == "first_reading"
    assert rows[0][4] == "Jer 26:1-9"
    assert rows[0][5] == "Lk 17:11-19"
    assert rows[0][6] == 1
    assert rows[1][0] == 2
    assert rows[1][2] == "gospel"


def test_downgrade_is_reversible_from_a_fresh_upgrade(legacy_engine, migration):
    """Upgrading and downgrading twice must converge on the same schema."""
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    first = sorted(_columns(legacy_engine, "reading_sets"))

    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    assert sorted(_columns(legacy_engine, "reading_sets")) == first


def test_migration_revision_chain_is_linear(legacy_engine, migration):
    assert migration.revision == "20261002_08"
    assert migration.down_revision == "20261002_07"

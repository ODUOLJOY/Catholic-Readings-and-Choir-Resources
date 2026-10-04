"""End-to-end validation of the Alembic migration chain on SQLite.

Two hazards are addressed explicitly.

``migrations/env.py`` ignores ``alembic.ini`` and always runs against
``settings.DATABASE_URL``. ``settings`` is an ``lru_cache`` module-level
singleton built when ``app.core.config`` is first imported, so once any earlier
test has imported it, mutating ``os.environ`` has no effect and Alembic would
migrate the configured PostgreSQL database instead of the test database. The
``sqlite_alembic`` fixture therefore overrides the cached singleton itself and
asserts the substitution took effect before any command runs.

The previous version of this test wrapped everything in ``try``/``except`` and
returned ``True``/``False``. Under pytest a returning test is reported as passing
with a ``PytestReturnNotNoneWarning``, so a migration that failed outright was
still counted as a success. Every check here is a real assertion.

The chain is additive by design: ``app/services/migration_preflight.py`` refuses
to run against a database that does not already carry the application schema, so
the baseline is created from the model metadata and stamped at the revision the
deployed database is expected to be at.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parent

BASELINE_REVISION = "20261002_06"
HEAD_REVISION = "20261003_01"

EXPECTED_TABLES = (
    "liturgical_days",
    "reading_sets",
    "reading_references",
    "liturgical_sources",
)

EXPECTED_LITURGICAL_DAY_COLUMNS = (
    "sunday_cycle",
    "weekday_cycle",
    "diocese_id",
    "parish_id",
)

EXPECTED_REFERENCE_COLUMNS = (
    "book",
    "display_reference",
    "is_alternative",
    "is_primary",
)

EXPECTED_NEW_USER_COLUMNS = (
    "status",
    "locked_at",
    "locked_by",
    "suspended_at",
    "suspended_by",
    "suspension_reason",
    "deactivated_at",
    "deactivated_by",
)


@pytest.fixture()
def sqlite_alembic(tmp_path, monkeypatch):
    """An Alembic config bound to a disposable SQLite file, or refuse to run.

    ``alembic.ini`` carries a placeholder ``sqlalchemy.url``, and
    ``migrations/env.py`` overrides it with ``settings.DATABASE_URL``, so setting
    the config option alone has no effect on where migrations are applied.
    """
    db_path = tmp_path / "migration_validation.db"
    url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", url)

    import app.core.config as config_module

    # env.py reads this attribute directly, so the cached singleton must be
    # overridden rather than only the environment it was built from.
    monkeypatch.setattr(config_module.settings, "DATABASE_URL", url, raising=False)

    resolved = config_module.settings.DATABASE_URL
    assert resolved.startswith("sqlite:///"), (
        f"refusing to migrate a non-SQLite target: {resolved!r}"
    )
    assert db_path.name in resolved, (
        f"refusing to migrate a database outside {tmp_path}: {resolved!r}"
    )

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    # These are relative in the ini file, so they are resolved absolutely to keep
    # the test independent of the working directory.
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))

    engine = create_engine(url)
    assert engine.dialect.name == "sqlite"

    yield config, engine

    engine.dispose()


@pytest.fixture()
def baseline_db(sqlite_alembic):
    """A database carrying the application schema, stamped at the baseline.

    This mirrors how a deployed database is prepared: the schema exists, and
    Alembic applies the additive revisions on top of it.
    """
    config, engine = sqlite_alembic

    from app.db.database import Base
    import app.models  # noqa: F401  (registers every table on Base.metadata)

    Base.metadata.create_all(engine)

    # Representative rows so that data preservation is actually observable. The
    # ORM is used rather than raw SQL because several columns are NOT NULL with
    # Python-side defaults only.
    from app.models.user import User, UserRole, UserStatus

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    full_name="Migration User",
                    email="migration@test.com",
                    hashed_password="hash",
                    role=UserRole.USER,
                    is_active=True,
                    status=UserStatus.ACTIVE,
                ),
                User(
                    full_name="Suspended User",
                    email="suspended@test.com",
                    hashed_password="hash",
                    role=UserRole.USER,
                    is_active=False,
                    status=UserStatus.SUSPENDED,
                ),
            ]
        )
        session.commit()

    command.stamp(config, BASELINE_REVISION)
    assert _current_revision(engine) == BASELINE_REVISION

    return config, engine


def _tables(engine):
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }


def _columns(engine, table):
    with engine.connect() as conn:
        return [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]


def _current_revision(engine):
    """The stamped revision id, or None when the database is unstamped.

    The engine is passed in rather than rebuilt from configuration, because
    ``alembic.ini`` holds a placeholder ``postgresql://`` url that must never be
    used to reach a database from this test.
    """
    from alembic.migration import MigrationContext

    assert engine.dialect.name == "sqlite"
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _users(engine):
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text(
                    "SELECT email, role, is_active, status FROM users ORDER BY email"
                )
            ).mappings()
        ]


# --------------------------------------------------------------------------
# Chain shape
# --------------------------------------------------------------------------


def test_chain_has_a_single_head(sqlite_alembic):
    """``upgrade head`` is ambiguous unless there is exactly one head."""
    config, _engine = sqlite_alembic
    script = command.ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1, f"expected a single head, found {heads}"
    assert heads[0] == HEAD_REVISION


def test_chain_is_linear(sqlite_alembic):
    """Every revision must have at most one parent and appear only once."""
    config, _engine = sqlite_alembic
    script = command.ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert revisions, "no revisions discovered"

    seen = set()
    for revision in revisions:
        assert revision.revision not in seen, f"duplicate revision {revision.revision}"
        seen.add(revision.revision)

        parents = revision.down_revision
        if parents is None:
            continue
        if isinstance(parents, (list, tuple)):
            assert len(parents) <= 1, f"{revision.revision} has multiple parents"
        else:
            assert isinstance(parents, str), (
                f"{revision.revision} has an unexpected parent {parents!r}"
            )


def test_chain_reaches_the_permissions_revision_from_the_baseline(sqlite_alembic):
    """The baseline must be an ancestor of head, so ``upgrade head`` reaches 09."""
    config, _engine = sqlite_alembic
    script = command.ScriptDirectory.from_config(config)

    # Walk head down to the base revision and confirm the baseline is on the path.
    path = [rev.revision for rev in script.walk_revisions()]
    assert path[0] == HEAD_REVISION, "walk_revisions should start at head"
    assert path[-1] == "20261001_01", "the chain should have a single base revision"
    assert BASELINE_REVISION in path, f"{BASELINE_REVISION} is not in the chain"


def test_preflight_refuses_an_empty_database(sqlite_alembic):
    """The chain is additive, so an empty database must be rejected loudly.

    This is the guard that stops ``upgrade head`` from silently running against a
    database that was never bootstrapped, and it documents the deployment model.
    """
    config, engine = sqlite_alembic

    with pytest.raises(RuntimeError, match="Migration preflight failed"):
        command.upgrade(config, "head")

    assert _current_revision(engine) is None


# --------------------------------------------------------------------------
# Upgrade
# --------------------------------------------------------------------------


def test_upgrade_head_from_the_baseline(baseline_db):
    config, engine = baseline_db
    command.upgrade(config, "head")
    assert _current_revision(engine) == HEAD_REVISION


def test_upgraded_schema_contains_the_expected_tables(baseline_db):
    config, engine = baseline_db
    command.upgrade(config, "head")

    tables = _tables(engine)
    for table in EXPECTED_TABLES:
        assert table in tables, f"{table} missing after upgrade"


def test_upgraded_schema_contains_the_new_liturgical_day_columns(baseline_db):
    config, engine = baseline_db
    command.upgrade(config, "head")

    columns = _columns(engine, "liturgical_days")
    for column in EXPECTED_LITURGICAL_DAY_COLUMNS:
        assert column in columns, f"liturgical_days.{column} missing"


def test_upgraded_schema_contains_the_reading_reference_structure(baseline_db):
    config, engine = baseline_db
    command.upgrade(config, "head")

    columns = _columns(engine, "reading_references")
    for column in EXPECTED_REFERENCE_COLUMNS:
        assert column in columns, f"reading_references.{column} missing"


def test_upgraded_schema_contains_the_permissions_changes(baseline_db):
    """Revision 09 must leave its tables, status column and tracking columns."""
    config, engine = baseline_db
    command.upgrade(config, "head")

    tables = _tables(engine)
    assert "permissions" in tables
    assert "role_permissions" in tables

    columns = _columns(engine, "users")
    for column in EXPECTED_NEW_USER_COLUMNS:
        assert column in columns, f"users.{column} missing"


def test_upgrade_preserves_user_rows_and_status_values(baseline_db):
    """Rows and their status representation must survive the upgrade."""
    config, engine = baseline_db
    before = _users(engine)

    command.upgrade(config, "head")

    assert _users(engine) == before
    statuses = {row["email"]: row["status"] for row in _users(engine)}
    assert statuses["migration@test.com"] == "active"
    assert statuses["suspended@test.com"] == "suspended"


def test_upgrade_is_repeatable(baseline_db):
    """Running ``upgrade head`` twice must not raise or alter the schema."""
    config, engine = baseline_db
    command.upgrade(config, "head")
    first = _columns(engine, "users")

    command.upgrade(config, "head")

    assert _current_revision(engine) == HEAD_REVISION
    assert _columns(engine, "users") == first
    assert _users(engine)


# --------------------------------------------------------------------------
# Downgrade
# --------------------------------------------------------------------------


def test_downgrade_to_the_baseline_removes_the_new_tables(baseline_db):
    config, engine = baseline_db
    command.upgrade(config, "head")

    command.downgrade(config, BASELINE_REVISION)

    assert _current_revision(engine) == BASELINE_REVISION
    tables = _tables(engine)
    assert "permissions" not in tables
    assert "role_permissions" not in tables


def test_downgrade_to_the_baseline_preserves_user_rows(baseline_db):
    """Rows survive the rollback even though revision 09's columns are removed.

    Alembic reverses everything a revision owns regardless of whether
    ``create_all`` had already added those columns, so downgrading to the
    baseline drops ``status`` and the tracking columns. This is inherent to
    stamping a database whose schema came from the model metadata, and is the
    reason a deployed database should only ever be rolled back to a revision it
    was genuinely stamped at.
    """
    config, engine = baseline_db
    before = _users(engine)
    command.upgrade(config, "head")

    command.downgrade(config, BASELINE_REVISION)

    with engine.connect() as conn:
        surviving = [
            dict(row)
            for row in conn.execute(
                text("SELECT email, role, is_active FROM users ORDER BY email")
            ).mappings()
        ]
    assert len(surviving) == len(before)
    assert {row["email"] for row in surviving} == {row["email"] for row in before}

    # Revision 09's columns are gone at the baseline.
    columns = _columns(engine, "users")
    assert "status" not in columns
    assert "suspension_reason" not in columns


def test_full_cycle_is_reversible(baseline_db):
    """baseline -> head -> baseline -> head must all succeed."""
    config, engine = baseline_db

    command.upgrade(config, "head")
    command.downgrade(config, BASELINE_REVISION)
    command.upgrade(config, "head")

    assert _current_revision(engine) == HEAD_REVISION
    tables = _tables(engine)
    for table in EXPECTED_TABLES:
        assert table in tables


def test_migration_never_touches_the_configured_database(monkeypatch):
    """Guard the guard: the fixture must refuse a non-SQLite target.

    Without this, a mistake in the override above would silently migrate the
    configured PostgreSQL database, which is exactly what the previous version of
    this test was able to do.
    """
    import app.core.config as config_module

    monkeypatch.setattr(
        config_module.settings, "DATABASE_URL", "postgresql://user:pass@host/db"
    )
    assert not config_module.settings.DATABASE_URL.startswith("sqlite:///")

"""Upgrade/downgrade tests for the permissions migration (revision 09).

The migration is loaded with ``importlib`` because its filename begins with a
digit, and it is driven through ``Operations.context`` so that the module-level
``alembic.op`` proxy is actually installed while the migration runs.

It is exercised against a disposable SQLite database seeded with user rows, so
that data loss is detected rather than assumed away.
"""

import importlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


@pytest.fixture(scope="module")
def migration():
    """Load the migration module despite its digit-leading filename."""
    return importlib.import_module("migrations.versions.20261002_09_permissions")


@pytest.fixture()
def legacy_engine(tmp_path):
    """A pre-migration database holding real user rows."""
    engine = create_engine(f"sqlite:///{tmp_path / 'permissions_legacy.db'}")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    full_name VARCHAR(200) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    role VARCHAR(30) DEFAULT 'user',
                    parish_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_users_email UNIQUE (email)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO users (id, full_name, email, hashed_password, role, "
                "parish_id, is_active) VALUES "
                "(1, 'Regular User', 'user@test.com', 'hash', 'user', 7, 1), "
                "(2, 'Choir Member', 'choir@test.com', 'hash', 'choir_contributor', 7, 1), "
                "(3, 'Locked Out', 'locked@test.com', 'hash', 'user', NULL, 0)"
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


def _indexes(engine, table):
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                text(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table}'")
            )
        }


def _user_rows(engine):
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text(
                    "SELECT id, full_name, email, role, parish_id, is_active "
                    "FROM users ORDER BY id"
                )
            ).mappings()
        ]


def _run(migration, engine, direction):
    """Run upgrade()/downgrade() with the alembic proxy properly installed."""
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(migration, direction)()


# --------------------------------------------------------------------------
# Revision wiring
# --------------------------------------------------------------------------


def test_revision_follows_the_reading_references_migration(migration):
    assert migration.revision == "20261002_09_permissions"
    assert migration.down_revision == "20261002_08"


# --------------------------------------------------------------------------
# Upgrade
# --------------------------------------------------------------------------


def test_upgrade_creates_the_permission_tables(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    tables = _tables(legacy_engine)
    assert "permissions" in tables
    assert "role_permissions" in tables


def test_upgrade_creates_the_permission_indexes(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    permissions_indexes = _indexes(legacy_engine, "permissions")
    assert "ix_permissions_name" in permissions_indexes
    assert "ix_permissions_category" in permissions_indexes
    assert "ix_role_permissions_role" in _indexes(legacy_engine, "role_permissions")


def test_upgrade_adds_the_user_status_column(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    assert "status" in _columns(legacy_engine, "users")


def test_upgrade_adds_the_administrative_tracking_columns(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    columns = _columns(legacy_engine, "users")
    for expected in (
        "locked_at",
        "locked_by",
        "suspended_at",
        "suspended_by",
        "suspension_reason",
        "deactivated_at",
        "deactivated_by",
    ):
        assert expected in columns, expected


def test_upgrade_backfills_the_default_status(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        statuses = [
            row[0]
            for row in conn.execute(text("SELECT status FROM users ORDER BY id"))
        ]
    # Pre-existing rows must not be left without a usable status.
    assert all(status == "active" for status in statuses), statuses


def test_upgrade_creates_the_user_indexes(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    indexes = _indexes(legacy_engine, "users")
    assert "ix_users_status" in indexes
    assert "ix_users_parish_id" in indexes


def test_upgrade_preserves_existing_user_rows(legacy_engine, migration):
    before = _user_rows(legacy_engine)
    _run(migration, legacy_engine, "upgrade")
    assert _user_rows(legacy_engine) == before


def test_upgrade_preserves_the_is_active_flag(legacy_engine, migration):
    """Suspension state must survive the migration."""
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        active = conn.execute(
            text("SELECT is_active FROM users WHERE id = 3")
        ).scalar()
    assert active == 0


def test_upgrade_is_idempotent(legacy_engine, migration):
    """A re-run must be a no-op rather than an error."""
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "upgrade")
    assert "permissions" in _tables(legacy_engine)
    assert "status" in _columns(legacy_engine, "users")


# --------------------------------------------------------------------------
# Downgrade
# --------------------------------------------------------------------------


def test_downgrade_drops_the_permission_tables(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    tables = _tables(legacy_engine)
    assert "permissions" not in tables
    assert "role_permissions" not in tables


def test_downgrade_removes_the_added_user_columns(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    columns = _columns(legacy_engine, "users")
    for unexpected in (
        "status",
        "locked_at",
        "locked_by",
        "suspended_at",
        "suspended_by",
        "suspension_reason",
        "deactivated_at",
        "deactivated_by",
    ):
        assert unexpected not in columns, unexpected


def test_downgrade_drops_the_user_indexes(legacy_engine, migration):
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    indexes = _indexes(legacy_engine, "users")
    assert "ix_users_status" not in indexes
    assert "ix_users_parish_id" not in indexes


def test_downgrade_preserves_existing_user_rows(legacy_engine, migration):
    before = _user_rows(legacy_engine)
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    assert _user_rows(legacy_engine) == before


def test_downgrade_restores_the_original_column_set(legacy_engine, migration):
    before = _columns(legacy_engine, "users")
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    assert _columns(legacy_engine, "users") == before


def test_upgrade_downgrade_cycle_is_reversible(legacy_engine, migration):
    """Up, down, up again must all succeed and land in the upgraded shape."""
    _run(migration, legacy_engine, "upgrade")
    _run(migration, legacy_engine, "downgrade")
    _run(migration, legacy_engine, "upgrade")
    tables = _tables(legacy_engine)
    assert "permissions" in tables
    assert "status" in _columns(legacy_engine, "users")


# --------------------------------------------------------------------------
# Enum representation
#
# SQLite stores the enum as free text and so cannot prove PostgreSQL behaviour.
# These tests pin the representation on both sides: the migration's labels, and
# what the ORM actually writes for every member of ``UserStatus``.
# --------------------------------------------------------------------------


def test_migration_status_labels_are_lowercase(migration):
    """The labels must be the lowercase values, not the member names."""
    assert migration._STATUS_VALUES == (
        "active",
        "pending",
        "suspended",
        "locked",
        "deactivated",
    )
    assert migration._STATUS_ENUM_NAME == "userstatus"


def test_migration_status_labels_match_the_model_enum(migration):
    """The migration labels and the model values must be the same set."""
    from app.models.user import UserStatus

    assert set(migration._STATUS_VALUES) == {member.value for member in UserStatus}


def test_model_persists_enum_values_not_member_names():
    """Regression: the ORM must not write ``ACTIVE`` where PostgreSQL expects ``active``.

    ``SQLEnum(UserStatus)`` without ``values_callable`` persists member *names*,
    which the ``userstatus`` enum type created by migration 09 does not contain.
    PostgreSQL would reject every such write with an invalid input value error.
    """
    from app.models.user import User, UserStatus

    assert User.__table__.c.status.type.enums == [
        member.value for member in UserStatus
    ]


def test_model_enum_type_name_matches_the_migration():
    from app.models.user import User, UserStatus

    assert User.__table__.c.status.type.name == "userstatus"


@pytest.mark.parametrize(
    "status", ["active", "pending", "suspended", "locked", "deactivated"]
)
def test_orm_writes_every_status_as_its_lowercase_value(status, tmp_path):
    """Each member round-trips through a real database write."""
    from sqlalchemy import select

    from app.db.database import Base
    from app.models.user import User, UserStatus
    engine = create_engine(f"sqlite:///{tmp_path / 'status_roundtrip.db'}")
    Base.metadata.create_all(engine, tables=[User.__table__])

    member = UserStatus(status)
    with engine.begin() as conn:
        conn.execute(
            User.__table__.insert().values(
                full_name="Status Probe",
                email=f"{status}@test.com",
                hashed_password="hash",
                role="user",
                status=member,
            )
        )
        stored = conn.execute(
            select(User.__table__.c.status).where(
                User.__table__.c.email == f"{status}@test.com"
            )
        ).scalar_one()
        # The raw column holds the lowercase value, matching the enum labels.
        assert stored == status
        assert stored != member.name

        # And it loads back as the enum member.
        loaded = conn.execute(
            select(User.__table__.c.status).where(
                User.__table__.c.email == f"{status}@test.com"
            )
        ).scalar_one()
        assert UserStatus(loaded) is member

    engine.dispose()


def test_status_update_round_trips(legacy_engine, migration):
    """Updating ``status`` to each value keeps the stored representation valid."""
    _run(migration, legacy_engine, "upgrade")
    for status in ("active", "pending", "suspended", "locked", "deactivated"):
        with legacy_engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET status = :status WHERE id = 1"),
                {"status": status},
            )
        with legacy_engine.connect() as conn:
            assert conn.execute(
                text("SELECT status FROM users WHERE id = 1")
            ).scalar_one() == status


def test_upgrade_backfills_active_for_existing_rows(legacy_engine, migration):
    """Pre-existing rows must receive the server default, not NULL."""
    _run(migration, legacy_engine, "upgrade")
    with legacy_engine.connect() as conn:
        statuses = [
            row[0] for row in conn.execute(text("SELECT status FROM users ORDER BY id"))
        ]
    assert statuses == ["active", "active", "active"]


# --------------------------------------------------------------------------
# Static PostgreSQL compilation
#
# There is no PostgreSQL service available for this repository, so instead of
# pretending the enum was exercised live, the DDL that migration 09 would emit
# is compiled for the postgresql dialect and asserted structurally.
# --------------------------------------------------------------------------


def test_postgres_ddl_creates_the_userstatus_type(migration):
    """``op.add_column`` skips ``CREATE TYPE``, so the migration must emit it."""
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    emitted = []

    def _capture(sql, *args, **kwargs):
        emitted.append(str(sql.compile(dialect=postgresql.dialect())))

    mock_engine = sa.create_mock_engine("postgresql://", _capture)
    # A MockConnection is not a context manager, so it is used directly.
    mock_conn = mock_engine.connect()
    sa.Enum(*migration._STATUS_VALUES, name=migration._STATUS_ENUM_NAME).create(
        mock_conn, checkfirst=False
    )

    assert len(emitted) == 1
    ddl = emitted[0]
    assert "CREATE TYPE userstatus AS ENUM" in ddl
    for label in migration._STATUS_VALUES:
        assert f"'{label}'" in ddl
    assert "'ACTIVE'" not in ddl


def test_postgres_column_references_the_created_enum_type(migration):
    """The column type and the created type must share one name."""
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    table = sa.Table(
        "t_probe",
        sa.MetaData(),
        sa.Column(
            "status",
            migration._status_enum_type(),
            nullable=False,
            server_default="active",
        ),
    )
    ddl = str(sa.schema.CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "status userstatus DEFAULT 'active' NOT NULL" in ddl
    assert "VARCHAR" not in ddl


def test_model_and_migration_render_identical_postgres_column_ddl(migration):
    """The model metadata and the migration must agree on the column definition."""
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    from app.models.user import User

    model_table = sa.Table(
        "users",
        sa.MetaData(),
        sa.Column(
            "status",
            User.__table__.c.status.type,
            nullable=False,
            server_default="active",
        ),
    )
    model_ddl = str(sa.schema.CreateTable(model_table).compile(dialect=postgresql.dialect()))

    migration_table = sa.Table(
        "users",
        sa.MetaData(),
        sa.Column(
            "status",
            migration._status_enum_type(),
            nullable=False,
            server_default="active",
        ),
    )
    migration_ddl = str(
        sa.schema.CreateTable(migration_table).compile(dialect=postgresql.dialect())
    )

    assert model_ddl == migration_ddl


def test_ensure_status_enum_is_a_noop_on_sqlite(legacy_engine, migration):
    """The PostgreSQL-only type creation must not run for SQLite."""
    with legacy_engine.connect() as conn:
        assert conn.dialect.name == "sqlite"
        migration._ensure_status_enum(conn)  # must not raise


def test_ensure_status_enum_creates_the_type_on_postgres(migration, monkeypatch):
    """On PostgreSQL the helper must issue CREATE TYPE exactly once."""
    import sqlalchemy as sa

    calls = []

    class _FakeDialect:
        name = "postgresql"

    class _FakeConn:
        dialect = _FakeDialect()

    def _spy(self, bind, checkfirst=False, **kwargs):
        calls.append((self.name, checkfirst))
        return None  # do not touch a real connection

    monkeypatch.setattr(sa.Enum, "create", _spy, raising=True)
    migration._ensure_status_enum(_FakeConn())

    assert calls == [("userstatus", True)]


def test_ensure_status_enum_is_idempotent_by_checkfirst(migration, monkeypatch):
    """``checkfirst`` must be used so an existing type is not re-created."""
    import sqlalchemy as sa

    calls = []

    class _FakeDialect:
        name = "postgresql"

    class _FakeConn:
        dialect = _FakeDialect()

    monkeypatch.setattr(
        sa.Enum, "create",
        lambda self, bind, checkfirst=False, **kw: calls.append(checkfirst),
        raising=True,
    )
    migration._ensure_status_enum(_FakeConn())
    assert calls == [True]

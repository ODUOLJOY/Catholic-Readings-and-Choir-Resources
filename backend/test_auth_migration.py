import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect
from sqlalchemy.pool import StaticPool


def _users_only_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    Table("users", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)
    return engine


def test_refresh_session_migration_works_on_sqlite():
    engine = _users_only_engine()
    migration = importlib.import_module(
        "migrations.versions.20261002_04_add_refresh_sessions"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

    inspector = inspect(engine)
    assert "refresh_sessions" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("refresh_sessions")}
    assert {
        "id",
        "user_id",
        "token_hash",
        "jti",
        "user_agent",
        "ip_address",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "created_at",
    } <= columns

    # The created_at server default must be valid on SQLite (no now() function).
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO refresh_sessions (user_id, token_hash, jti, expires_at) "
            "VALUES (1, 'hash', 'jti', '2030-01-01 00:00:00')"
        )
        created_at = connection.exec_driver_sql(
            "SELECT created_at FROM refresh_sessions"
        ).first()
    assert created_at is not None and created_at[0] is not None

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    assert "refresh_sessions" not in inspect(engine).get_table_names()
    engine.dispose()

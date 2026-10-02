import importlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
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


def test_external_identity_migration_works_on_sqlite():
    engine = _users_only_engine()
    migration = importlib.import_module(
        "migrations.versions.20261002_06_external_identities"
    )

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            # Idempotent: a second run must be a no-op.
            migration.upgrade()

    inspector = inspect(engine)
    assert "external_identities" in inspector.get_table_names()
    columns = {
        column["name"]
        for column in inspector.get_columns("external_identities")
    }
    assert {
        "id",
        "user_id",
        "provider",
        "provider_subject",
        "email_at_link",
        "created_at",
        "updated_at",
    } <= columns

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO external_identities "
            "(user_id, provider, provider_subject) VALUES (1, 'google', 'sub-1')"
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO external_identities "
                "(user_id, provider, provider_subject) VALUES (1, 'google', 'sub-1')"
            )

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    assert "external_identities" not in inspect(engine).get_table_names()
    engine.dispose()

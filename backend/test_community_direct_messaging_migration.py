import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
)
from sqlalchemy.pool import StaticPool


def _legacy_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    Table(
        "community_conversations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("scope_type", String(20), nullable=False),
        Column("scope_id", Integer, nullable=False),
        Column("group_id", Integer),
        Column("created_by", Integer, nullable=False),
        Column("is_active", Boolean, nullable=False),
        Column("created_at", DateTime(timezone=True)),
        CheckConstraint(
            "scope_type IN ('parish', 'group')",
            name="ck_community_conversation_scope",
        ),
    )
    Table(
        "conversation_members",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("conversation_id", Integer, nullable=False),
        Column("user_id", Integer, nullable=False),
        Column("is_muted", Boolean, nullable=False),
        Column("joined_at", DateTime(timezone=True)),
    )
    metadata.create_all(engine)
    return engine


def test_direct_messaging_migration_upgrades_legacy_sqlite():
    engine = _legacy_engine()
    migration = importlib.import_module(
        "migrations.versions.20261002_05_community_direct_messaging"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()

    inspect_engine = inspect(engine)
    conversation_columns = {
        column["name"]
        for column in inspect_engine.get_columns("community_conversations")
    }
    assert {"conversation_type", "direct_key"} <= conversation_columns
    member_columns = {
        column["name"]
        for column in inspect_engine.get_columns("conversation_members")
    }
    assert {"last_read_message_id", "last_read_at"} <= member_columns

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO community_conversations "
            "(conversation_type, scope_type, scope_id, direct_key, created_by, is_active) "
            "VALUES ('direct', NULL, NULL, '1:2', 1, 1)"
        )
        row = connection.exec_driver_sql(
            "SELECT conversation_type, direct_key "
            "FROM community_conversations"
        ).first()
    assert row[0] == "direct"
    assert row[1] == "1:2"

    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM community_conversations")
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    assert "conversation_type" not in {
        column["name"]
        for column in inspect(engine).get_columns("community_conversations")
    }
    engine.dispose()


def test_direct_messaging_migration_refuses_downgrade_with_data():
    engine = _legacy_engine()
    migration = importlib.import_module(
        "migrations.versions.20261002_05_community_direct_messaging"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        connection.exec_driver_sql(
            "INSERT INTO community_conversations "
            "(conversation_type, scope_type, scope_id, direct_key, created_by, is_active) "
            "VALUES ('direct', NULL, NULL, '5:6', 1, 1)"
        )
        with Operations.context(MigrationContext.configure(connection)):
            try:
                migration.downgrade()
            except RuntimeError as error:
                assert "direct conversations" in str(error)
            else:  # pragma: no cover
                raise AssertionError("Downgrade should refuse while direct data exists.")
    engine.dispose()

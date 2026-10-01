import importlib
from io import StringIO
from datetime import datetime, timezone

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community
import app.models.choir
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base
from app.models.community import ParishMembership
from app.models.choir import ChoirResource
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User
from app.services.migration_preflight import verify_legacy_schema


def test_community_migration_backfills_legacy_parishes_idempotently():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    legacy_tables = [
        Diocese.__table__,
        Deanery.__table__,
        Parish.__table__,
        User.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=legacy_tables)
    legacy_resource_table = Table(
        "choir_resources",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("title", String(255), nullable=False),
        Column("description", Text),
        Column("category", String(100), nullable=False),
        Column("language", String(20), nullable=False),
        Column("file_url", String(500), nullable=False),
        Column("file_type", String(50), nullable=False),
        Column("file_size", Integer),
        Column("composer", String(255)),
        Column("lyrics", Text),
        Column("duration", Integer),
        Column("is_approved", Boolean),
        Column("is_published", Boolean),
        Column("uploaded_by", Integer),
        Column("rating", Integer),
        Column("download_count", Integer),
        Column("created_at", DateTime(timezone=True)),
        Column("updated_at", DateTime(timezone=True)),
        Column("approved_at", DateTime(timezone=True)),
        Column("published_at", DateTime(timezone=True)),
    )
    legacy_resource_table.create(engine)

    with Session(engine) as db:
        diocese = Diocese(name="Migration Diocese", code="migration-diocese")
        db.add(diocese)
        db.flush()
        deanery = Deanery(
            name="Migration Deanery",
            code="migration-deanery",
            diocese_id=diocese.id,
        )
        db.add(deanery)
        db.flush()
        parish = Parish(
            name="Migration Parish",
            code="migration-parish",
            diocese_id=diocese.id,
            deanery_id=deanery.id,
        )
        db.add(parish)
        db.flush()
        affiliated = User(
            full_name="Legacy member",
            email="legacy@example.org",
            hashed_password="not-a-real-password-hash",
            parish_id=parish.id,
        )
        unassigned = User(
            full_name="Unassigned member",
            email="unassigned@example.org",
            hashed_password="not-a-real-password-hash",
        )
        db.add_all([affiliated, unassigned])
        db.flush()
        db.execute(
            legacy_resource_table.insert().values(
                title="Legacy global resource",
                category="Mass",
                language="English",
                file_url="/media/pdfs/legacy.pdf",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                download_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        affiliated_id = affiliated.id
        parish_id = parish.id

    migration = importlib.import_module(
        "migrations.versions.20261001_01_community"
    )
    choir_scope_migration = importlib.import_module(
        "migrations.versions.20261001_02_choir_resource_parish"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            choir_scope_migration.upgrade()

    with Session(engine) as db:
        memberships = db.query(ParishMembership).all()
        assert len(memberships) == 1
        assert memberships[0].user_id == affiliated_id
        assert memberships[0].parish_id == parish_id
        assert memberships[0].status == "pending"
        legacy_resource = db.query(ChoirResource).one()
        assert legacy_resource.parish_id is None

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            choir_scope_migration.downgrade()
            assert "parish_id" not in {
                column["name"]
                for column in inspect(connection).get_columns("choir_resources")
            }
            migration.downgrade()
    table_names = set(inspect(engine).get_table_names())
    assert "role_assignments" not in table_names
    assert "parish_memberships" not in table_names
    assert {"users", "parishes", "dioceses", "deaneries"} <= table_names
    engine.dispose()


def test_migration_preflight_fails_before_any_schema_change():
    engine = create_engine("sqlite://")
    migration = importlib.import_module("migrations.versions.20261001_01_community")
    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="Migration preflight failed"):
            verify_legacy_schema(connection)
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="Migration preflight failed"):
                migration.upgrade()
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_migration_chain_generates_postgresql_offline_sql():
    output = StringIO()
    migration_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={
            "as_sql": True,
            "literal_binds": True,
            "output_buffer": output,
        },
    )
    community_migration = importlib.import_module(
        "migrations.versions.20261001_01_community"
    )
    choir_migration = importlib.import_module(
        "migrations.versions.20261001_02_choir_resource_parish"
    )
    with Operations.context(migration_context):
        community_migration.upgrade()
        choir_migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE role_assignments" in sql
    assert "ALTER TABLE choir_resources ADD COLUMN parish_id INTEGER" in sql
    assert "FOREIGN KEY(parish_id) REFERENCES parishes (id)" in sql

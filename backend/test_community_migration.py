import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base
from app.models.community import ParishMembership
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User


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
        db.commit()
        affiliated_id = affiliated.id
        parish_id = parish.id

    migration = importlib.import_module(
        "migrations.versions.20261001_01_community"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()

    with Session(engine) as db:
        memberships = db.query(ParishMembership).all()
        assert len(memberships) == 1
        assert memberships[0].user_id == affiliated_id
        assert memberships[0].parish_id == parish_id
        assert memberships[0].status == "pending"

    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    table_names = set(inspect(engine).get_table_names())
    assert "role_assignments" not in table_names
    assert "parish_memberships" not in table_names
    assert {"users", "parishes", "dioceses", "deaneries"} <= table_names
    engine.dispose()

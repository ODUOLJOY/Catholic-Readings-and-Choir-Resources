"""Restore the baseline columns the additive chain assumes already exist.

Revision ID: 20261006_01
Revises: d6ea5b253a0e

Why this sits below the chain
-----------------------------
The database is stamped ``d6ea5b253a0e``, an id that exists nowhere in this
repository, so ``alembic upgrade head`` originally failed with ``Can't locate
revision``. That id is now an empty root (``20261006_00_legacy_baseline``) and
this revision follows it. The stamp is therefore left exactly as found -- it
genuinely *is* at that point in its history -- while the sixteen real migrations
above it can run. Rewriting the stamp to a known id would have silently skipped
all sixteen.

This revision is the one that actually runs first, because Alembic applies
revisions *after* the stamped version.

What it changes
---------------
Nothing but missing baseline columns. ``app.services.migration_preflight``
requires a schema older than this database happens to be -- specifically
``users.parish_id`` -- and every migration in the chain calls that preflight
before doing anything, so the chain cannot start until it is satisfied.

Column types and foreign keys are copied from the mapped models rather than
re-stated here, so this cannot drift from the definitions in ``app.models``.
Everything is guarded by inspection: re-running against an up-to-date database
is a no-op, and this never drops or rewrites a column that already exists.

Deliberately *not* done here: the rest of the schema delta. Columns that the
chain itself adds (``choir_resources.storage_key``, the hierarchy columns, ...)
must stay absent until their own revision runs, or that revision fails.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261006_01"
down_revision = "d6ea5b253a0e"
branch_labels = None
depends_on = None

# Imported lazily inside upgrade(): importing model modules at collection time
# pulls in the whole metadata graph.
PREFLIGHT_REQUIREMENTS = {
    "users": {"id", "parish_id"},
    "dioceses": {"id"},
    "deaneries": {"id", "diocese_id"},
    "parishes": {"id", "diocese_id", "deanery_id"},
    "readings": {"id", "reading_date", "language"},
    "choir_resources": {"id"},
}


def _model_table(table_name: str):
    from app.db.database import Base

    import app.models  # noqa: F401  -- registers every mapped table

    return Base.metadata.tables[table_name]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name, required in PREFLIGHT_REQUIREMENTS.items():
        if table_name not in existing_tables:
            # Tables the chain itself creates are not this migration's business.
            continue
        present = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(required - present)
        if not missing:
            continue

        model = _model_table(table_name)
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}

        for column_name in missing:
            source = model.c[column_name]
            op.add_column(
                table_name,
                sa.Column(
                    column_name,
                    source.type,
                    nullable=source.nullable,
                ),
            )
            if source.foreign_keys:
                for fk in source.foreign_keys:
                    op.create_foreign_key(
                        f"fk_{table_name}_{column_name}_{fk.target_fullname}",
                        table_name,
                        fk.target_fullname.split(".")[0],
                        [column_name],
                        [fk.column.name],
                    )
            if source.index and source.name not in existing_indexes:
                op.create_index(
                    f"ix_{table_name}_{column_name}",
                    table_name,
                    [column_name],
                )


def downgrade() -> None:
    # Additive only: dropping these columns would break the migration chain that
    # depends on them and cannot be undone safely on a shared database.
    raise NotImplementedError(
        "d6ea5b253a0e is an additive baseline repair and has no downgrade."
    )

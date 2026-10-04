"""Add structured metadata columns to ``choir_resources``.

Revision ID: 20261002_11
Revises: 20261002_10
Create Date: 2026-10-02

Adds the structured-metadata fields the choir-library product vision requires
(``alternative_title``, ``author``, ``arranger``, ``voice_part``, ``season``,
``key_signature``, ``tempo``) plus indexes on the two columns most often used
for list filtering (``voice_part`` and ``season``).

Every column is nullable with no server default, so existing rows are preserved
unchanged and the change is safe on a populated table. Both ``upgrade`` and
``downgrade`` are idempotent -- they introspect the live schema before acting --
so re-running ``upgrade head`` (or rolling back further than one step) is safe
on SQLite and PostgreSQL alike.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import Column
from sqlalchemy import String

# revision identifiers, used by Alembic.
revision = "20261002_11"
down_revision = "20261002_10"
branch_labels = None
depends_on = None

TABLE_NAME = "choir_resources"

NEW_COLUMNS = [
    Column("alternative_title", String(255), nullable=True),
    Column("author", String(255), nullable=True),
    Column("arranger", String(255), nullable=True),
    Column("voice_part", String(50), nullable=True),
    Column("season", String(50), nullable=True),
    Column("key_signature", String(50), nullable=True),
    Column("tempo", String(50), nullable=True),
]

# (index name, ordered column names). Names mirror ChoirResource's ``index=True``
# declarations so ``Base.metadata.create_all`` and this migration produce a
# congruent schema.
NEW_INDEXES = [
    ("ix_choir_resources_voice_part", ["voice_part"]),
    ("ix_choir_resources_season", ["season"]),
]

DROP_INDEXES = [name for name, _cols in NEW_INDEXES]


def _existing(bind, table_name):
    """Return (columns, indexes) for ``table_name`` or (set(), set()) if absent."""
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set(), set()
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    return columns, indexes


def upgrade() -> None:
    bind = op.get_bind()
    existing_cols, existing_idx = _existing(bind, TABLE_NAME)
    if not existing_cols and not existing_idx:
        # The table does not exist at this point; nothing to add.
        return

    for column in NEW_COLUMNS:
        if column.name not in existing_cols:
            op.add_column(TABLE_NAME, column)

    # Recompute the live index set after any columns were added.
    existing_idx = {ix["name"] for ix in sa.inspect(bind).get_indexes(TABLE_NAME)}
    for name, cols in NEW_INDEXES:
        if name not in existing_idx:
            op.create_index(name, TABLE_NAME, cols)


def downgrade() -> None:
    bind = op.get_bind()
    existing_cols, existing_idx = _existing(bind, TABLE_NAME)
    if not existing_cols and not existing_idx:
        return

    # Drop indexes before the columns they reference.
    for name in DROP_INDEXES:
        if name in existing_idx:
            op.drop_index(name, table_name=TABLE_NAME)

    drop_columns = [col.name for col in NEW_COLUMNS if col.name in existing_cols]
    if drop_columns:
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            for column_name in drop_columns:
                batch_op.drop_column(column_name)

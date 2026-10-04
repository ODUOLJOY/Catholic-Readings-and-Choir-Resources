"""Add server-side facet indexes to ``choir_resources``.

Revision ID: 20261002_12
Revises: 20261002_11
Create Date: 2026-10-02

Adds the three indexes that back the server-side faceted list endpoint
(``/api/choir/`` query-parameter filters): one each on ``language``,
``key_signature`` and ``tempo``. These columns already exist (added by rev11);
this revision only adds indexes.

Mirroring rev11, every operation is idempotent: the live schema is introspected
before acting, so re-running ``upgrade head`` (or rolling back further than one
step) is safe on SQLite and PostgreSQL alike. The index names mirror the
``index=True`` declarations on ``ChoirResource`` so ``Base.metadata.create_all``
and the migration chain produce a congruent schema.

PostgreSQL notes: these are plain B-tree indexes on text columns -- no ENUM,
no type changes, no named constraints beyond the indexes themselves, and the
indexes are dropped (never the columns) on downgrade.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20261002_12"
down_revision = "20261002_11"
branch_labels = None
depends_on = None

TABLE_NAME = "choir_resources"

# (index name, ordered column names). Names mirror ChoirResource's ``index=True``
# declarations so ``Base.metadata.create_all`` and this migration produce a
# congruent schema.
NEW_INDEXES = [
    ("ix_choir_resources_language", ["language"]),
    ("ix_choir_resources_key_signature", ["key_signature"]),
    ("ix_choir_resources_tempo", ["tempo"]),
]

DROP_INDEXES = [name for name, _cols in NEW_INDEXES]


def _existing_indexes(bind, table_name):
    """Return the set of index names for ``table_name`` (empty if table absent)."""
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        # The table is created by an earlier revision; nothing to do yet.
        return

    existing_idx = {idx["name"] for idx in inspector.get_indexes(TABLE_NAME)}
    for name, cols in NEW_INDEXES:
        if name not in existing_idx:
            op.create_index(name, TABLE_NAME, cols)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return

    existing_idx = {idx["name"] for idx in inspector.get_indexes(TABLE_NAME)}
    for name in DROP_INDEXES:
        if name in existing_idx:
            op.drop_index(name, table_name=TABLE_NAME)

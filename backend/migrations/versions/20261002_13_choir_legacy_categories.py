"""Remap legacy choir category labels to the canonical 27.

Revision ID: 20261002_13
Revises: 20261002_12
Create Date: 2026-10-03

Single source of truth for the 27 canonical choir categories lives in
``app/constants/choir_categories.py`` (frontend mirror:
``frontend/src/config/choirCategories.ts``). Resources created before that list
existed may carry legacy labels such as ``"Kyrie Eleison"`` or ``"Holy Holy"``.
The browse endpoint already matches legacy labels to canonical filters via
:func:`app.constants.choir_categories.categories_matching_filter`, so legacy rows
are visible -- but they are cleaner to operate on if the unambiguous ones are
normalised in storage.

This migration rewrites every legacy alias in ``CATEGORY_ALIASES`` to its
canonical equivalent. Values that :func:`normalize_category` would map to
``"Others"`` (``"Mass"``, ``"Eucharistic"``, ``"Other"``, etc.) are included so
the storage column matches what a fresh upload would store. Truly unknown
labels (typos not in the alias map) are left untouched: they surface through
the ``"Others"`` browse bucket and an admin can correct them manually via the
edit screen, which normalises on save.

The operation is idempotent: after the first run no row carries a mapped
alias, so re-running ``upgrade head`` updates zero rows. The downgrade is a
no-op: the legacy labels were never canonical values, so reversing the remap
could collide with rows that legitimately use the canonical label and must not
be undone.
"""
import sqlalchemy as sa
from alembic import op

from app.constants.choir_categories import CATEGORY_ALIASES

# revision identifiers, used by Alembic.
revision = "20261002_13"
down_revision = "20261002_12"
branch_labels = None
depends_on = None

TABLE_NAME = "choir_resources"
CATEGORY_COLUMN = "category"


def _table_exists(bind) -> bool:
    inspector = sa.inspect(bind)
    return TABLE_NAME in set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        # The table is created by an earlier revision; nothing to do yet.
        return

    # Parameterised per (alias, canonical) pair so each UPDATE is a single
    # equality predicate -- this matches the existing index on ``category``
    # (ix_choir_resources_category) and stays cheap on large tables.
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias == canonical:
            # Defensive: the map should never map a label to itself, but skip
            # rather than issue a redundant no-op UPDATE if it ever does.
            continue
        bind.execute(
            sa.text(
                f"UPDATE {TABLE_NAME} "
                f"SET {CATEGORY_COLUMN} = :canonical "
                f"WHERE {CATEGORY_COLUMN} = :alias"
            ).bindparams(canonical=canonical, alias=alias)
        )


def downgrade() -> None:
    # Intentionally a no-op. See module docstring: reversing the remap could
    # rewrite rows that legitimately use the canonical label back to a legacy
    # alias, which would break the canonical-only validation enforced on new
    # uploads and edits. The remap is a one-way data normalisation.
    return

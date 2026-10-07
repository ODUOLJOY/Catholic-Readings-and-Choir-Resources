"""Placeholder for the unknown legacy baseline the database was stamped with.

Revision ID: d6ea5b253a0e
Revises:

This revision exists solely so the stamped marker resolves. The target database
reported ``d6ea5b253a0e`` as its current version, but that id was never present
in this repository, so Alembic refused to do anything at all:

    Can't locate revision identified by 'd6ea5b253a0e'

Rewriting the stamp to a known id instead would have skipped the sixteen real
migrations that have never run against this database. Claiming the id as an
empty root keeps the stamp honest -- the database genuinely *is* at this point
in its history -- while letting the chain above it execute.

It intentionally changes nothing: the schema it represents was produced by
tooling no longer in the repo, and nothing here can know what it contained.

It is already applied on the stamped database, so its ``upgrade`` will not run
there. On a database created from scratch, ``schema_bootstrap`` stamps ``head``
directly and this revision is likewise never executed.
"""

from __future__ import annotations

from alembic import op

revision = "d6ea5b253a0e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

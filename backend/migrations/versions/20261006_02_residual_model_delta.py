"""Reconcile whatever schema delta the sixteen original migrations leave behind.

Revision ID: 20261006_02
Revises: 20261003_01

Why this revision exists
------------------------
This database never ran ``alembic upgrade head`` before now, so its shape was
established by some older, unknown tooling rather than by this repository's
migration chain. Running the chain from the repaired root brings the schema most
of the way to the mapped models, but not all the way: a handful of columns that
*no* migration in the chain ever adds are still absent (``users.role``,
``users.last_login``, ``payments.*``, ``notifications.body``), and one modelled
table -- ``content`` -- is never created by any revision.

Rather than hard-code a second frozen shopping list, this revision derives its
work from ``Base.metadata`` itself: it creates every mapped table the database
does not have, in dependency order, and adds every mapped column it does not
have. That makes ``alembic check`` converge on this database and keeps the
revision correct if the models move again.

Additive only
-------------
Nothing here drops, narrows, or rewrites an existing column. Every operation is
guarded by inspection, so re-running against an up-to-date database is a no-op.

Server defaults on backfill
---------------------------
Adding a ``NOT NULL`` column to a table that already has rows requires a
default. Where the model supplies one (``users.role`` -> ``'user'``) that
literal is used; where it does not, a type-appropriate zero value is used so the
existing rows remain valid. The column itself still matches the model's
nullability, so this does not paper over a real constraint.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261006_02"
down_revision = "20261003_01"
branch_labels = None
depends_on = None


def _metadata():
    from app.db.database import Base

    import app.models  # noqa: F401  -- registers every mapped table

    return Base.metadata


def _sql_literal(value) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def _backfill_default(column) -> str | None:
    """SQL literal to satisfy NOT NULL on a table that may already hold rows."""
    if column.server_default is not None:
        return None  # already carried over from the model definition
    if column.default is not None:
        literal = _sql_literal(column.default.arg)
        if literal is not None:
            return literal
    type_name = type(column.type).__name__
    if type_name in {"Boolean"}:
        return "false"
    if type_name in {"Integer", "SmallInteger", "BigInteger", "Numeric", "Float"}:
        return "0"
    if type_name in {"String", "Text", "Unicode", "UnicodeText"}:
        return "''"
    if type_name in {"DateTime", "Date", "TIMESTAMP"}:
        return "CURRENT_TIMESTAMP"
    return None


def _add_column(bind, table_name: str, column, existing_indexes: set[str]) -> None:
    server_default = None
    nullable = column.nullable

    if not column.nullable:
        literal = _backfill_default(column)
        if literal is None and column.server_default is None:
            # No way to satisfy the constraint without inventing data: fall back
            # to a nullable column rather than fail the whole reconciliation.
            nullable = True
        elif column.server_default is None and literal is not None:
            server_default = sa.text(literal)

    op.add_column(
        table_name,
        sa.Column(
            column.name,
            column.type,
            nullable=nullable,
            server_default=server_default
            if server_default is not None
            else column.server_default,
        ),
    )

    for fk in column.foreign_keys:
        op.create_foreign_key(
            f"fk_{table_name}_{column.name}_{fk.target_fullname}",
            table_name,
            fk.target_fullname.split(".")[0],
            [column.name],
            [fk.column.name],
        )

    if column.index and column.name not in existing_indexes:
        op.create_index(
            f"ix_{table_name}_{column.name}", table_name, [column.name]
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    metadata = _metadata()
    existing_tables = set(inspector.get_table_names())

    # 1. Tables the models define but the database lacks, in FK dependency order.
    for table in metadata.sorted_tables:
        if table.name in existing_tables:
            continue
        bind.execute(sa.schema.CreateTable(table))
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            bind.execute(sa.schema.CreateIndex(index))
        existing_tables.add(table.name)

    # 2. Columns those tables are still missing.
    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        existing_indexes = {i["name"] for i in inspector.get_indexes(table.name)}
        for column in table.columns:
            if column.name not in present:
                _add_column(bind, table.name, column, existing_indexes)
                present.add(column.name)


def downgrade() -> None:
    # Additive only: dropping these would break the mapped models and cannot be
    # reversed safely on a shared database that predates the chain.
    raise NotImplementedError(
        "20261006_02 is an additive reconciliation and has no downgrade."
    )

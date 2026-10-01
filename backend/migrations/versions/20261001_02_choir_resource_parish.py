"""Add parish scope to choir resources.

Revision ID: 20261001_02
Revises: 20261001_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_02"
down_revision = "20261001_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    offline = op.get_context().as_sql
    if not offline:
        from app.services.migration_preflight import verify_legacy_schema

        verify_legacy_schema(op.get_bind())
    if offline:
        op.add_column(
            "choir_resources",
            sa.Column("parish_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_choir_resources_parish_id_parishes",
            "choir_resources",
            "parishes",
            ["parish_id"],
            ["id"],
        )
        op.create_index(
            "ix_choir_resources_parish_id",
            "choir_resources",
            ["parish_id"],
        )
        return
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.add_column(sa.Column("parish_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_choir_resources_parish_id_parishes",
            "parishes",
            ["parish_id"],
            ["id"],
        )
        batch_op.create_index("ix_choir_resources_parish_id", ["parish_id"])


def downgrade() -> None:
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.drop_index("ix_choir_resources_parish_id")
        batch_op.drop_constraint(
            "fk_choir_resources_parish_id_parishes",
            type_="foreignkey",
        )
        batch_op.drop_column("parish_id")

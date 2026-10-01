"""Track private choir-resource object storage keys.

Revision ID: 20261002_02
Revises: 20261002_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_02"
down_revision = "20261002_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not op.get_context().as_sql:
        from app.services.migration_preflight import verify_legacy_schema

        verify_legacy_schema(op.get_bind())
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.add_column(sa.Column("storage_key", sa.String(length=1000), nullable=True))
        batch_op.create_index("ix_choir_resources_storage_key", ["storage_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT id FROM choir_resources WHERE storage_key IS NOT NULL LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot downgrade while choir resources reference private object storage."
        )
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.drop_index("ix_choir_resources_storage_key")
        batch_op.drop_column("storage_key")

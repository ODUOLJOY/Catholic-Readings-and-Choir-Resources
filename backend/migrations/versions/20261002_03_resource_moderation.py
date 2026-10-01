"""Add review metadata to choir resources.

Revision ID: 20261002_03
Revises: 20261002_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_03"
down_revision = "20261002_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "moderation_status",
                sa.String(length=30),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_choir_resources_moderation_status",
            ["moderation_status"],
        )
        batch_op.create_foreign_key(
            "fk_choir_resources_reviewed_by_users",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        sa.text(
            "UPDATE choir_resources "
            "SET moderation_status = 'approved' "
            "WHERE is_approved IS TRUE OR is_published IS TRUE"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_review_history = bind.execute(
        sa.text(
            "SELECT id FROM choir_resources "
            "WHERE moderation_status = 'rejected' "
            "OR reviewed_by IS NOT NULL "
            "OR reviewed_at IS NOT NULL "
            "OR rejection_reason IS NOT NULL LIMIT 1"
        )
    ).first()
    if has_review_history:
        raise RuntimeError(
            "Cannot downgrade while choir resources contain moderation history."
        )
    with op.batch_alter_table("choir_resources") as batch_op:
        batch_op.drop_constraint(
            "fk_choir_resources_reviewed_by_users",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_choir_resources_moderation_status")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("moderation_status")

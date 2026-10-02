"""Add external identity table for federated sign-in (Google).

Revision ID: 20261002_06
Revises: 20261002_05
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_06"
down_revision = "20261002_05"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _create_table() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email_at_link", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identity_provider_subject",
        ),
    )
    op.create_index(
        op.f("ix_external_identities_id"),
        "external_identities",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_identities_user_id"),
        "external_identities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_identities_provider"),
        "external_identities",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_identities_provider_subject"),
        "external_identities",
        ["provider_subject"],
        unique=False,
    )


def _drop_table() -> None:
    op.drop_index(
        op.f("ix_external_identities_provider_subject"),
        table_name="external_identities",
    )
    op.drop_index(
        op.f("ix_external_identities_provider"),
        table_name="external_identities",
    )
    op.drop_index(
        op.f("ix_external_identities_user_id"),
        table_name="external_identities",
    )
    op.drop_index(
        op.f("ix_external_identities_id"),
        table_name="external_identities",
    )
    op.drop_table("external_identities")


def upgrade() -> None:
    if op.get_context().as_sql:
        _create_table()
        return

    bind = op.get_bind()
    if not _table_exists(bind, "external_identities"):
        _create_table()


def downgrade() -> None:
    if op.get_context().as_sql:
        _drop_table()
        return

    bind = op.get_bind()
    if _table_exists(bind, "external_identities"):
        _drop_table()

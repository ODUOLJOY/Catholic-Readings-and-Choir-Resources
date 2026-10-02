"""Add direct conversations and per-member read tracking.

Revision ID: 20261002_05
Revises: 20261002_04
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_05"
down_revision = "20261002_04"
branch_labels = None
depends_on = None

SCOPE_CHECK_NEW = (
    "(conversation_type = 'direct' AND scope_type IS NULL "
    "AND scope_id IS NULL AND direct_key IS NOT NULL) OR "
    "(conversation_type <> 'direct' AND scope_type IN ('parish', 'group') "
    "AND scope_id IS NOT NULL AND direct_key IS NULL)"
)


def _columns(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _upgrade_conversations() -> None:
    with op.batch_alter_table("community_conversations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "conversation_type",
                sa.String(length=20),
                nullable=False,
                server_default="scope",
            )
        )
        batch_op.add_column(
            sa.Column("direct_key", sa.String(length=80), nullable=True)
        )
        batch_op.alter_column(
            "scope_type",
            existing_type=sa.String(length=20),
            nullable=True,
        )
        batch_op.alter_column(
            "scope_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.drop_constraint(
            "ck_community_conversation_scope",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_community_conversation_scope",
            SCOPE_CHECK_NEW,
        )
        batch_op.create_unique_constraint(
            "uq_community_conversation_direct_key",
            ["direct_key"],
        )


def _upgrade_members() -> None:
    with op.batch_alter_table("conversation_members") as batch_op:
        batch_op.add_column(
            sa.Column("last_read_message_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "last_read_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def _downgrade_conversations() -> None:
    with op.batch_alter_table("community_conversations") as batch_op:
        batch_op.drop_constraint(
            "uq_community_conversation_direct_key",
            type_="unique",
        )
        batch_op.drop_constraint(
            "ck_community_conversation_scope",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_community_conversation_scope",
            "scope_type IN ('parish', 'group')",
        )
        batch_op.alter_column(
            "scope_type",
            existing_type=sa.String(length=20),
            nullable=False,
        )
        batch_op.alter_column(
            "scope_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.drop_column("direct_key")
        batch_op.drop_column("conversation_type")


def _downgrade_members() -> None:
    with op.batch_alter_table("conversation_members") as batch_op:
        batch_op.drop_column("last_read_at")
        batch_op.drop_column("last_read_message_id")


def upgrade() -> None:
    if op.get_context().as_sql:
        _upgrade_conversations()
        _upgrade_members()
        return

    bind = op.get_bind()
    if "conversation_type" not in _columns(bind, "community_conversations"):
        _upgrade_conversations()
    if "last_read_message_id" not in _columns(bind, "conversation_members"):
        _upgrade_members()


def downgrade() -> None:
    if op.get_context().as_sql:
        _downgrade_conversations()
        _downgrade_members()
        return

    bind = op.get_bind()
    if "conversation_type" in _columns(bind, "community_conversations"):
        direct = bind.execute(
            sa.text(
                "SELECT id FROM community_conversations "
                "WHERE conversation_type = 'direct' LIMIT 1"
            )
        ).first()
        if direct:
            raise RuntimeError(
                "Cannot downgrade while direct conversations exist."
            )
        _downgrade_conversations()
    if "last_read_message_id" in _columns(bind, "conversation_members"):
        _downgrade_members()

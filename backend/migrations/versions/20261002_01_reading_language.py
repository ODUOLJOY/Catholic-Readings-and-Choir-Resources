"""Allow one reading record per date and language.

Revision ID: 20261002_01
Revises: 20261001_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_01"
down_revision = "20261001_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not op.get_context().as_sql:
        from app.services.migration_preflight import verify_legacy_schema

        verify_legacy_schema(op.get_bind())

    op.drop_index("ix_readings_reading_date", table_name="readings")
    op.create_index("ix_readings_reading_date", "readings", ["reading_date"])
    op.create_index(
        "uq_readings_date_language",
        "readings",
        ["reading_date", "language"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT reading_date FROM readings "
            "GROUP BY reading_date HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Cannot downgrade reading languages while multiple languages share a date."
        )

    op.drop_index("uq_readings_date_language", table_name="readings")
    op.drop_index("ix_readings_reading_date", table_name="readings")
    op.create_index(
        "ix_readings_reading_date",
        "readings",
        ["reading_date"],
        unique=True,
    )

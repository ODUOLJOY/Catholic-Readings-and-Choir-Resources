"""Let a provisioned permission grant carry no human grantor.

Revision ID: 20261006_03
Revises: 20261006_02

Why
---
``permission_seed`` copies ``DEFAULT_ROLE_PERMISSIONS`` into ``role_permissions``
before any administrator has done anything. ``granted_by`` was declared
``NOT NULL`` with a foreign key to ``users.id``, so the seeder had only two
options: attribute those grants to a real person who did not make them, or
fabricate a user to hold the marker. It attempted a third -- a literal
``'system-seed'`` string -- which PostgreSQL rejected with
``invalid input syntax for type integer``, so seeding failed outright and every
role other than ``super_admin`` kept zero permissions.

``NULL`` says exactly what is true: no person granted this, the deploy did.
That mirrors ``RoleAssignment.revoked_by``, already nullable for the same
reason.

Additive: relaxing a constraint only widens what the table accepts. Existing
rows keep their grantor, and every non-seed writer passes a real ``user.id``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261006_03"
down_revision = "20261006_02"
branch_labels = None
depends_on = None

TABLE = "role_permissions"
COLUMN = "granted_by"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
    target = columns.get(COLUMN)
    if target is None or target["nullable"]:
        return

    # batch_alter_table issues a native ALTER on PostgreSQL and rebuilds the
    # table on SQLite, which has no DROP NOT NULL.
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.alter_column(
            COLUMN, existing_type=sa.Integer(), nullable=True
        )


def downgrade() -> None:
    # Restoring NOT NULL would fail on any database the seeder has already run
    # against, since those rows hold NULL grantors.
    raise NotImplementedError(
        "20261006_03 relaxes a constraint the seeder depends on and has no downgrade."
    )

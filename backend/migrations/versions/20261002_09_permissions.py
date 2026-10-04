"""Add permissions, enhanced user status, and audit log improvements.

SQLite cannot express ``ALTER TABLE ... ADD CONSTRAINT`` or ``ALTER TABLE ...
DROP COLUMN``, so the ``users`` changes are applied through alembic's batch
mode, which rebuilds the table. Self-referencing foreign keys are declared
inline on the new columns rather than through separate ``create_foreign_key``
calls, because the original form omitted the referenced column list and never
executed.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261002_09_permissions"
down_revision = "20261002_08"  # Reading references
branch_labels = None
depends_on = None


# Administrative tracking columns added to ``users``. Each entry is
# (column name, type, whether it references ``users.id``).
_TRACKING_COLUMNS = (
    ("locked_at", sa.DateTime(timezone=True), False),
    ("locked_by", sa.Integer(), True),
    ("suspended_at", sa.DateTime(timezone=True), False),
    ("suspended_by", sa.Integer(), True),
    ("suspension_reason", sa.String(500), False),
    ("deactivated_at", sa.DateTime(timezone=True), False),
    ("deactivated_by", sa.Integer(), True),
)

_INDEXES = (
    ("ix_users_status", "users", ["status"]),
    ("ix_users_parish_id", "users", ["parish_id"]),
)

# The ``users.status`` enum. These labels are lowercase by design and must match
# the ``values_callable`` mapping on ``models.user.User.status``, otherwise the ORM
# would write member names such as ``ACTIVE`` and PostgreSQL would reject them.
_STATUS_VALUES = ("active", "pending", "suspended", "locked", "deactivated")
_STATUS_ENUM_NAME = "userstatus"


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _ensure_status_enum(bind) -> None:
    """Create the ``userstatus`` enum type on PostgreSQL.

    ``op.add_column`` does not run SQLAlchemy's ``CREATE TYPE`` hooks, so a
    PostgreSQL deployment would otherwise fail with
    ``type "userstatus" does not exist``. SQLite has no enum types and stores the
    value as text, so the call is dialect-guarded. ``checkfirst`` keeps the
    migration idempotent and safe when the type was already created by
    ``Base.metadata.create_all`` from the model metadata.
    """
    if bind.dialect.name == "postgresql":
        sa.Enum(*_STATUS_VALUES, name=_STATUS_ENUM_NAME).create(bind, checkfirst=True)


def _status_enum_type() -> sa.Enum:
    return sa.Enum(*_STATUS_VALUES, name=_STATUS_ENUM_NAME)


def _column_names(bind, table_name: str) -> set:
    return {col["name"] for col in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table_name)}


def _create_index_if_missing(bind, index_name: str, table_name: str, columns) -> None:
    if index_name not in _index_names(bind, table_name):
        op.create_index(index_name, table_name, columns)


def upgrade():
    bind = op.get_bind()

    # Create permissions table
    if not _table_exists(bind, "permissions"):
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_permissions_name", "permissions", ["name"])
        op.create_index("ix_permissions_category", "permissions", ["category"])

    # Create role_permissions table
    if not _table_exists(bind, "role_permissions"):
        op.create_table(
            "role_permissions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(50), nullable=False),
            sa.Column(
                "permission_id",
                sa.Integer(),
                sa.ForeignKey("permissions.id"),
                nullable=False,
            ),
            sa.Column(
                "granted_by",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "granted_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("role", "permission_id", name="uq_role_permission"),
        )
        op.create_index("ix_role_permissions_role", "role_permissions", ["role"])

    present = _column_names(bind, "users")
    missing = [name for name, _, _ in _TRACKING_COLUMNS if name not in present]
    needs_status = "status" not in present

    if needs_status or missing:
        # Rebuild ``users`` to add the columns. Existing rows keep their values,
        # and the non-null ``status`` column is backfilled by its server default.
        if needs_status:
            _ensure_status_enum(bind)
        with op.batch_alter_table("users") as batch_op:
            if needs_status:
                batch_op.add_column(
                    sa.Column(
                        "status",
                        _status_enum_type(),
                        nullable=False,
                        server_default="active",
                    )
                )
            for name, column_type, references_users in _TRACKING_COLUMNS:
                if name in missing:
                    if references_users:
                        # The foreign key must be named: alembic's batch mode
                        # rejects unnamed constraints when it rebuilds the table.
                        batch_op.add_column(
                            sa.Column(
                                name,
                                column_type,
                                sa.ForeignKey("users.id", name=f"fk_users_{name}"),
                                nullable=True,
                            )
                        )
                    else:
                        batch_op.add_column(sa.Column(name, column_type, nullable=True))

            # A status column that already exists may still hold NULLs if it was
            # added without a default by an earlier partial run.
            if not needs_status:
                op.execute(sa.text("UPDATE users SET status = 'active' WHERE status IS NULL"))

    # Add indexes for performance. These are applied after the rebuild because
    # batch mode may recreate the underlying table.
    for index_name, table_name, columns in _INDEXES:
        _create_index_if_missing(bind, index_name, table_name, columns)


def downgrade():
    bind = op.get_bind()

    # Drop indexes that this migration created.
    for index_name, table_name, _columns in _INDEXES:
        if index_name in _index_names(bind, table_name):
            op.drop_index(index_name, table_name)

    present = _column_names(bind, "users")
    added = [name for name, _, _ in _TRACKING_COLUMNS if name in present]
    has_status = "status" in present

    if added or has_status:
        # Dropping the columns also drops the self-referencing foreign keys that
        # were declared alongside them. SQLite needs the batch rebuild to do it.
        #
        # The PostgreSQL ``userstatus`` type is deliberately left in place. A
        # rollback should not destroy a type that ``Base.metadata.create_all`` may
        # have created independently of this migration, and re-running ``upgrade``
        # recreates it via ``checkfirst``. An orphaned enum type is harmless.
        with op.batch_alter_table("users") as batch_op:
            for name in added:
                batch_op.drop_column(name)
            if has_status:
                batch_op.drop_column("status")

    if _table_exists(bind, "role_permissions"):
        if "ix_role_permissions_role" in _index_names(bind, "role_permissions"):
            op.drop_index("ix_role_permissions_role", "role_permissions")
        op.drop_table("role_permissions")

    if _table_exists(bind, "permissions"):
        for index_name in ("ix_permissions_name", "ix_permissions_category"):
            if index_name in _index_names(bind, "permissions"):
                op.drop_index(index_name, "permissions")
        op.drop_table("permissions")

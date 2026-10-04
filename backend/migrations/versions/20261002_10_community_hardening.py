"""Harden the social/community subsystem.

Adds message edit tracking, threaded suggestion replies, suggestion workflow
timestamps, and a structurally complete + organizationally scoped moderation
table. ``content_reports`` previously existed only through startup
``create_all``; this revision creates it for migration-only deployments.

Every rebuildable operation carries an explicit ``copy_from`` table definition.
SQLite reflection of a previously Alembic-rebuilt table loses foreign key
constraint names, and a subsequent rebuild then dies with "Constraint must have
a name". Passing the authoritative definition keeps upgrades, downgrades, and
repeated cycles deterministic on SQLite while leaving PostgreSQL on native
``ALTER TABLE`` statements.

Revision ID: 20261002_10
Revises: 20261002_09_permissions
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_10"
down_revision = "20261002_09_permissions"
branch_labels = None
depends_on = None


MESSAGES_TABLE = "community_messages"
SUGGESTIONS_TABLE = "community_suggestions"
REPORTS_TABLE = "content_reports"
BLOCKS_TABLE = "member_blocks"
REPLIES_TABLE = "community_suggestion_replies"

SUGGESTION_STATUS_CONSTRAINT = "ck_suggestion_status"
SUGGESTION_STATUS_CHECK_OLD = (
    "status IN ('submitted', 'under_review', 'in_discussion', "
    "'accepted', 'implemented', 'declined', 'archived')"
)
SUGGESTION_STATUS_CHECK_NEW = (
    "status IN ('submitted', 'under_review', 'needs_information', "
    "'in_discussion', 'accepted', 'escalated', 'implemented', "
    "'declined', 'archived')"
)

BLOCKED_ID_INDEX = "ix_member_blocks_blocked_id"
REPORT_INDEXES_DROPPED_ON_DOWNGRADE = (
    "ix_content_reports_resource",
    "ix_content_reports_status_scope",
)


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def _tables(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table_name: str) -> set:
    if table_name not in _tables(bind):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _indexes(bind, table_name: str) -> set:
    if table_name not in _tables(bind):
        return set()
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _normalize(sql) -> str:
    """Collapse a reflected constraint expression into a comparable form."""
    text = " ".join(str(sql).split()).lower()
    while text.startswith("(") and text.endswith(")") and len(text) > 1:
        text = " ".join(text[1:-1].split())
    return text


def _status_checks(bind) -> list:
    """Return ``(name, sqltext)`` for every ``status`` check on suggestions."""
    if SUGGESTIONS_TABLE not in _tables(bind):
        return []
    return [
        (check["name"], check.get("sqltext") or "")
        for check in sa.inspect(bind).get_check_constraints(SUGGESTIONS_TABLE)
        if check["name"]
        and _normalize(check.get("sqltext") or "").startswith("status in")
    ]


# ---------------------------------------------------------------------------
# Authoritative column definitions
# ---------------------------------------------------------------------------


def _messages_columns(edit_fields: bool) -> list:
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(
                "community_conversations.id",
                name="fk_community_messages_conversation_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_community_messages_sender_id"),
            nullable=False,
        ),
        sa.Column(
            "reply_to_id",
            sa.Integer(),
            sa.ForeignKey(
                "community_messages.id",
                name="fk_community_messages_reply_to_id",
            ),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    ]
    if edit_fields:
        columns.append(
            sa.Column(
                "is_edited",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        columns.append(sa.Column("edited_at", sa.DateTime(), nullable=True))
    columns.append(
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
    return columns


def _message_edit_columns() -> list:
    keep = {column.name for column in _messages_columns(edit_fields=False)}
    return [
        column
        for column in _messages_columns(edit_fields=True)
        if column.name not in keep
    ]


def _suggestion_columns(workflow: bool) -> list:
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submitter_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_community_suggestions_submitter_id"
            ),
            nullable=True,
        ),
        sa.Column(
            "is_anonymous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column(
            "reviewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_community_suggestions_reviewer_id"),
            nullable=True,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
    ]
    if workflow:
        columns.extend(_suggestion_workflow_columns())
    columns.append(
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
    columns.append(
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
    return columns


def _suggestion_workflow_columns() -> list:
    return [
        sa.Column(
            "assigned_to",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_community_suggestions_assigned_to"
            ),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
    ]


def _report_base_columns() -> list:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reporter_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_content_reports_reporter_id"),
            nullable=True,
        ),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "reviewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_content_reports_reviewer_id"),
            nullable=True,
        ),
    ]


def _report_legacy_columns() -> list:
    """The shape this revision is applied to: base columns plus ``resolution``."""
    return _report_base_columns() + [
        sa.Column("resolution", sa.String(length=100), nullable=True)
    ]


def _report_moderation_columns() -> list:
    return [
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("scope_type", sa.String(length=20), nullable=True),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column(
            "assigned_to",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_content_reports_assigned_to"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("moderation_action", sa.String(length=40), nullable=True),
    ]


def _report_columns(moderation: bool) -> list:
    columns = _report_legacy_columns()
    if moderation:
        columns.extend(_report_moderation_columns())
    return columns


# ---------------------------------------------------------------------------
# Operation helpers
# ---------------------------------------------------------------------------


def _is_sqlite(bind) -> bool:
    return bind.dialect.name == "sqlite"


def _copy_from(bind, table_name: str, columns, checks=(), drop_indexes=()) -> sa.Table:
    """Build the authoritative pre-operation table definition.

    Columns and check constraints are declared here rather than reflected, and
    indexes are carried over from the live database so a rebuild neither invents
    nor loses one.
    """
    live_indexes = []
    if table_name in _tables(bind):
        live_indexes = [
            index
            for index in sa.inspect(bind).get_indexes(table_name)
            if index.get("name") and index["name"] not in drop_indexes
        ]
    constraints = [
        sa.CheckConstraint(sqltext, name=name) for name, sqltext in checks
    ]
    return sa.Table(
        table_name,
        sa.MetaData(),
        *(list(columns) + constraints),
        *[
            sa.Index(
                index["name"],
                *index["column_names"],
                unique=bool(index.get("unique")),
            )
            for index in live_indexes
        ],
    )


def _rebuild(
    bind,
    table_name: str,
    *,
    copy_columns,
    add=(),
    drop=(),
    checks=(),
    drop_checks=(),
    create_checks=(),
    drop_indexes=(),
) -> None:
    """Recreate ``table_name`` from an explicit definition.

    ``copy_columns`` describes the table as it exists *before* the operation so
    Alembic can carry rows across by column name.
    """
    copy_from = _copy_from(bind, table_name, copy_columns, checks, drop_indexes)
    with op.batch_alter_table(
        table_name, copy_from=copy_from, recreate="always"
    ) as batch_op:
        for column in add:
            batch_op.add_column(column)
        for name in drop:
            batch_op.drop_column(name)
        for name in drop_checks:
            batch_op.drop_constraint(name, type_="check")
        for name, sqltext in create_checks:
            batch_op.create_check_constraint(name, sqltext)


def _drop_columns(
    bind,
    table_name: str,
    names,
    drop_indexes=(),
    offline: bool = False,
    checks=(),
    copy_columns=None,
) -> None:
    """Drop indexes then columns using native statements where possible."""
    if offline:
        for name in drop_indexes:
            op.drop_index(name, table_name=table_name)
        for name in names:
            op.drop_column(table_name, name)
        return

    live_indexes = _indexes(bind, table_name)
    for name in drop_indexes:
        if name in live_indexes:
            op.drop_index(name, table_name=table_name)

    if _is_sqlite(bind):
        present = [name for name in names if name in _columns(bind, table_name)]
        if present:
            _rebuild(
                bind,
                table_name,
                copy_columns=copy_columns if copy_columns is not None else _full_columns(table_name),
                checks=checks,
                drop=present,
                drop_indexes=drop_indexes,
            )
        return

    live_columns = _columns(bind, table_name)
    for name in names:
        if name in live_columns:
            op.drop_column(table_name, name)


def _full_columns(table_name: str) -> list:
    """The complete post-upgrade shape of each rebuilt table.

    Used as ``copy_from`` when dropping columns, because Alembic carries rows
    across by column name and therefore needs the pre-operation shape.
    """
    if table_name == MESSAGES_TABLE:
        return _messages_columns(edit_fields=True)
    if table_name == SUGGESTIONS_TABLE:
        return _suggestion_columns(workflow=True)
    if table_name == REPORTS_TABLE:
        return _report_columns(moderation=True)
    raise ValueError("no authoritative definition for " + table_name)


def _swap_status_check(bind, target_sql: str, *, offline: bool, workflow: bool) -> None:
    """Point ``ck_suggestion_status`` at ``target_sql``."""
    if offline:
        with op.batch_alter_table(SUGGESTIONS_TABLE) as batch_op:
            try:
                batch_op.drop_constraint(SUGGESTION_STATUS_CONSTRAINT, type_="check")
            except (NotImplementedError, ValueError):
                pass
            batch_op.create_check_constraint(SUGGESTION_STATUS_CONSTRAINT, target_sql)
        return

    checks = _status_checks(bind)
    stale = [
        name
        for name, sqltext in checks
        if _normalize(sqltext) != _normalize(target_sql)
    ]
    if checks and not stale:
        return

    if _is_sqlite(bind):
        _rebuild(
            bind,
            SUGGESTIONS_TABLE,
            copy_columns=_suggestion_columns(workflow=workflow),
            create_checks=[(SUGGESTION_STATUS_CONSTRAINT, target_sql)],
        )
        return

    for name, _ in checks:
        op.drop_constraint(name, SUGGESTIONS_TABLE, type_="check")
    op.create_check_constraint(
        SUGGESTION_STATUS_CONSTRAINT, SUGGESTIONS_TABLE, target_sql
    )


# ---------------------------------------------------------------------------
# Table creation for migration-only deployments
# ---------------------------------------------------------------------------


def _create_suggestion_replies() -> None:
    op.create_table(
        REPLIES_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "suggestion_id",
            sa.Integer(),
            sa.ForeignKey(
                "community_suggestions.id",
                name="fk_community_suggestion_replies_suggestion_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id", name="fk_community_suggestion_replies_author_id"
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_community_suggestion_replies_suggestion_created",
        REPLIES_TABLE,
        ["suggestion_id", "created_at"],
    )


def _create_content_reports() -> None:
    """Create the moderation table for deployments built from migrations only."""
    op.create_table(REPORTS_TABLE, *_report_columns(moderation=True))
    op.create_index("ix_content_reports_reporter_id", REPORTS_TABLE, ["reporter_id"])
    op.create_index("ix_content_reports_status", REPORTS_TABLE, ["status"])
    op.create_index(
        "ix_content_reports_status_scope",
        REPORTS_TABLE,
        ["status", "scope_type", "scope_id"],
    )
    op.create_index(
        "ix_content_reports_resource",
        REPORTS_TABLE,
        ["resource_type", "resource_id"],
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    offline = op.get_context().as_sql
    bind = op.get_bind()

    if offline:
        for column in _message_edit_columns():
            op.add_column(MESSAGES_TABLE, column)
        for column in _suggestion_workflow_columns():
            op.add_column(SUGGESTIONS_TABLE, column)
        _swap_status_check(
            bind, SUGGESTION_STATUS_CHECK_NEW, offline=True, workflow=True
        )
        _create_content_reports()
        op.create_index(BLOCKED_ID_INDEX, BLOCKS_TABLE, ["blocked_id"])
        _create_suggestion_replies()
        return

    message_additions = [
        column
        for column in _message_edit_columns()
        if column.name not in _columns(bind, MESSAGES_TABLE)
    ]
    for column in message_additions:
        op.add_column(MESSAGES_TABLE, column)

    suggestion_columns = _columns(bind, SUGGESTIONS_TABLE)
    workflow_additions = [
        column
        for column in _suggestion_workflow_columns()
        if column.name not in suggestion_columns
    ]
    if workflow_additions:
        if _is_sqlite(bind):
            _rebuild(
                bind,
                SUGGESTIONS_TABLE,
                copy_columns=_suggestion_columns(workflow=False),
                add=workflow_additions,
                checks=_status_checks(bind),
            )
        else:
            for column in workflow_additions:
                op.add_column(SUGGESTIONS_TABLE, column)
    _swap_status_check(
        bind, SUGGESTION_STATUS_CHECK_NEW, offline=False, workflow=True
    )

    if REPORTS_TABLE not in _tables(bind):
        _create_content_reports()
    else:
        report_columns = _columns(bind, REPORTS_TABLE)
        report_additions = [
            column
            for column in _report_moderation_columns()
            if column.name not in report_columns
        ]
        if report_additions:
            if _is_sqlite(bind):
                _rebuild(
                    bind,
                    REPORTS_TABLE,
                    copy_columns=_report_legacy_columns(),
                    add=report_additions,
                )
            else:
                for column in report_additions:
                    op.add_column(REPORTS_TABLE, column)
        report_indexes = _indexes(bind, REPORTS_TABLE)
        for name, columns in (
            ("ix_content_reports_status_scope", ["status", "scope_type", "scope_id"]),
            ("ix_content_reports_resource", ["resource_type", "resource_id"]),
        ):
            if name not in report_indexes:
                op.create_index(name, REPORTS_TABLE, columns)

    if BLOCKED_ID_INDEX not in _indexes(bind, BLOCKS_TABLE):
        op.create_index(BLOCKED_ID_INDEX, BLOCKS_TABLE, ["blocked_id"])

    if REPLIES_TABLE not in _tables(bind):
        _create_suggestion_replies()


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    offline = op.get_context().as_sql
    bind = op.get_bind()

    if offline:
        for name in ("edited_at", "is_edited"):
            op.drop_column(MESSAGES_TABLE, name)
        for name in ("escalated_at", "resolved_at", "assigned_to"):
            op.drop_column(SUGGESTIONS_TABLE, name)
        _swap_status_check(
            bind, SUGGESTION_STATUS_CHECK_OLD, offline=True, workflow=False
        )
        op.drop_table(REPLIES_TABLE)
        op.drop_index(BLOCKED_ID_INDEX, table_name=BLOCKS_TABLE)
        _drop_columns(
            bind,
            REPORTS_TABLE,
            [column.name for column in _report_moderation_columns()],
            drop_indexes=REPORT_INDEXES_DROPPED_ON_DOWNGRADE,
            offline=True,
        )
        return

    tables = _tables(bind)

    if REPLIES_TABLE in tables:
        replies = bind.execute(
            sa.text("SELECT COUNT(*) FROM " + REPLIES_TABLE)
        ).scalar()
        if replies:
            raise RuntimeError(
                "Cannot downgrade while suggestion replies exist. "
                "Archive or delete them first."
            )
        op.drop_table(REPLIES_TABLE)

    if BLOCKED_ID_INDEX in _indexes(bind, BLOCKS_TABLE):
        op.drop_index(BLOCKED_ID_INDEX, table_name=BLOCKS_TABLE)

    if REPORTS_TABLE in tables:
        _drop_columns(
            bind,
            REPORTS_TABLE,
            [column.name for column in _report_moderation_columns()],
            drop_indexes=REPORT_INDEXES_DROPPED_ON_DOWNGRADE,
            copy_columns=_report_columns(moderation=True),
        )

    if SUGGESTIONS_TABLE in tables:
        _drop_columns(
            bind,
            SUGGESTIONS_TABLE,
            ["escalated_at", "resolved_at", "assigned_to"],
            checks=_status_checks(bind),
        )
        _swap_status_check(
            bind, SUGGESTION_STATUS_CHECK_OLD, offline=False, workflow=False
        )

    if MESSAGES_TABLE in tables:
        _drop_columns(bind, MESSAGES_TABLE, ["edited_at", "is_edited"])

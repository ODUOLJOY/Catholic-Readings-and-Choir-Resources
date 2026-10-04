"""Add structured reading references and improve liturgical calendar.

Revision ID: 20261002_08
Revises: 20261002_07

Two correctness properties this migration must hold, because it runs against
databases that already hold liturgical data:

* It is portable. ``ALTER TABLE ... ALTER COLUMN ... SET NOT NULL`` is not
  valid SQLite, so the NOT NULL tightening uses ``batch_alter_table``.
* It is non-destructive. ``reading_sets`` is rebuilt to move the free-text
  reading references into the new ``reading_references`` table, but the rows and
  the reference text are carried across rather than dropped.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_08"
down_revision = "20261002_07"
branch_labels = None
depends_on = None


# The four free-text reference columns on ``reading_sets`` before this
# migration, mapped to the structured ``reading_type`` they become.
_LEGACY_REFERENCE_COLUMNS = (
    ("first_reading_reference", "first_reading"),
    ("responsorial_psalm_reference", "responsorial_psalm"),
    ("second_reading_reference", "second_reading"),
    ("gospel_reference", "gospel"),
)


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set:
    return {col["name"] for col in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table_name)}


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(bind, table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(bind, index_name: str, table_name: str, columns) -> None:
    if index_name not in _index_names(bind, table_name):
        op.create_index(index_name, table_name, columns)


def _book_from_reference(reference: str) -> str:
    """Best-effort book name from a reference such as ``Jer 26:1-9``.

    Only the leading token is taken; the full original string is always stored
    verbatim in ``display_reference``, so nothing is invented and nothing is
    lost if the guess is imperfect.
    """
    head = (reference or "").strip().split(" ", 1)[0]
    return head[:100] or "Unknown"


def _create_reading_references_table() -> None:
    op.create_table(
        "reading_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reading_set_id", sa.Integer(), nullable=False),
        sa.Column("reading_type", sa.String(length=50), nullable=False),
        sa.Column("book", sa.String(length=100), nullable=False),
        sa.Column("chapter_start", sa.Integer(), nullable=True),
        sa.Column("verse_start", sa.String(length=50), nullable=True),
        sa.Column("chapter_end", sa.Integer(), nullable=True),
        sa.Column("verse_end", sa.String(length=50), nullable=True),
        sa.Column("display_reference", sa.String(length=255), nullable=False),
        sa.Column("psalm_number_variant", sa.String(length=50), nullable=True),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_alternative", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_optional", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("lectionary_number", sa.String(length=50), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["reading_set_id"],
            ["reading_sets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_reading_references_book", "book"),
        sa.Index("ix_reading_references_id", "id"),
        sa.Index("ix_reading_references_reading_type", "reading_type"),
    )


def _drop_reading_references_table() -> None:
    op.drop_index("ix_reading_references_reading_type", table_name="reading_references")
    op.drop_index("ix_reading_references_id", table_name="reading_references")
    op.drop_index("ix_reading_references_book", table_name="reading_references")
    op.drop_table("reading_references")


def _upgrade_liturgical_day() -> None:
    bind = op.get_bind()

    # Add new columns for liturgical cycles (nullable initially). Each column is
    # guarded so a re-run of this migration is a no-op rather than an error.
    _add_column_if_missing(
        bind, "liturgical_days", sa.Column("sunday_cycle", sa.String(length=5), nullable=True)
    )
    _add_column_if_missing(
        bind, "liturgical_days", sa.Column("weekday_cycle", sa.String(length=5), nullable=True)
    )
    _add_column_if_missing(
        bind, "liturgical_days", sa.Column("diocese_id", sa.Integer(), nullable=True)
    )
    _add_column_if_missing(
        bind, "liturgical_days", sa.Column("parish_id", sa.Integer(), nullable=True)
    )

    # Add index on verification_status
    _create_index_if_missing(
        bind,
        "ix_liturgical_days_verification_status",
        "liturgical_days",
        ["verification_status"],
    )

    # Data migration: copy liturgical_year to sunday_cycle, set default weekday_cycle
    op.execute(
        sa.text("UPDATE liturgical_days SET sunday_cycle = liturgical_year WHERE liturgical_year IS NOT NULL")
    )
    op.execute(
        sa.text("UPDATE liturgical_days SET weekday_cycle = 'I' WHERE weekday_cycle IS NULL")
    )

    # Make them non-nullable. SQLite cannot express this as a plain ALTER, so the
    # table is rebuilt by alembic's batch mode.
    present = _column_names(bind, "liturgical_days")
    with op.batch_alter_table("liturgical_days") as batch_op:
        if "sunday_cycle" in present:
            batch_op.alter_column(
                "sunday_cycle",
                existing_type=sa.String(length=5),
                nullable=False,
                server_default="A",
            )
        if "weekday_cycle" in present:
            batch_op.alter_column(
                "weekday_cycle",
                existing_type=sa.String(length=5),
                nullable=False,
                server_default="I",
            )

    # Keep liturgical_year for backward compatibility


def _downgrade_liturgical_day() -> None:
    # Batch mode is required for the column drops as well: SQLite has no
    # "DROP COLUMN" that alembic can rely on across versions.
    with op.batch_alter_table("liturgical_days") as batch_op:
        batch_op.drop_index("ix_liturgical_days_verification_status")
        batch_op.drop_column("parish_id")
        batch_op.drop_column("diocese_id")
        batch_op.drop_column("weekday_cycle")
        batch_op.drop_column("sunday_cycle")


def _backfill_reading_references(bind) -> int:
    """Move free-text references into ``reading_references`` before they are dropped.

    Runs in Python rather than SQL so that the same logic works on SQLite and
    PostgreSQL. Returns the number of rows written.
    """
    if not _table_exists(bind, "reading_references"):
        return 0

    existing_columns = _column_names(bind, "reading_sets")
    source_columns = [
        (column, reading_type)
        for column, reading_type in _LEGACY_REFERENCE_COLUMNS
        if column in existing_columns
    ]
    if not source_columns:
        return 0

    select_columns = ", ".join(["id", *[c for c, _ in source_columns]])
    rows = bind.execute(sa.text(f"SELECT {select_columns} FROM reading_sets")).fetchall()

    payload = []
    for row in rows:
        record = dict(zip(["id", *[c for c, _ in source_columns]], row))
        set_id = record["id"]
        for column, reading_type in source_columns:
            reference = (record.get(column) or "").strip()
            if not reference:
                continue
            payload.append(
                {
                    "reading_set_id": set_id,
                    "reading_type": reading_type,
                    "book": _book_from_reference(reference),
                    "display_reference": reference[:255],
                    "sequence": 0,
                    "is_alternative": False,
                    "is_optional": False,
                    "is_primary": True,
                }
            )

    if not payload:
        return 0

    bind.execute(
        sa.text(
            "INSERT INTO reading_references (reading_set_id, reading_type, book, "
            "display_reference, sequence, is_alternative, is_optional, is_primary) "
            "VALUES (:reading_set_id, :reading_type, :book, :display_reference, "
            ":sequence, :is_alternative, :is_optional, :is_primary)"
        ),
        payload,
    )
    return len(payload)


def _recreate_reading_sets_table() -> None:
    """Rebuild ``reading_sets`` in the new shape without losing any rows.

    The previous implementation dropped the table outright, which destroyed
    every existing reading set. Rows are copied into a replacement table and the
    reference text is preserved in ``reading_references`` beforehand.
    """
    bind = op.get_bind()

    # If the new shape is already in place there is nothing to rebuild. Without
    # this guard a re-run would rebuild the table a second time, which is
    # needless work and would re-derive the reference backfill.
    if "celebration_name" in _column_names(bind, "reading_sets"):
        return

    # Preserve the free-text references while the old columns still exist.
    _backfill_reading_references(bind)

    op.create_table(
        "reading_sets_rebuilt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("liturgical_day_id", sa.Integer(), nullable=False),
        sa.Column("reading_type", sa.String(length=50), nullable=False),
        sa.Column("selection_status", sa.String(length=50), nullable=False, server_default="weekday_default"),
        sa.Column("celebration_id", sa.Integer(), nullable=True),
        sa.Column("celebration_name", sa.String(length=255), nullable=True),
        sa.Column("lectionary_number", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("authority_level", sa.String(length=50), nullable=True),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="unverified"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["liturgical_day_id"], ["liturgical_days.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["liturgical_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Carry every row across. The two NOT NULL columns use COALESCE because the
    # legacy table allowed NULLs there.
    op.execute(
        sa.text(
            "INSERT INTO reading_sets_rebuilt (id, liturgical_day_id, reading_type, "
            "selection_status, celebration_id, celebration_name, lectionary_number, "
            "source_id, authority_level, verification_status, verified_at, "
            "created_at, updated_at) "
            "SELECT id, liturgical_day_id, reading_type, "
            "COALESCE(selection_status, 'weekday_default'), celebration_id, NULL, "
            "lectionary_number, source_id, authority_level, "
            "COALESCE(verification_status, 'unverified'), NULL, "
            "COALESCE(created_at, CURRENT_TIMESTAMP), "
            "COALESCE(updated_at, CURRENT_TIMESTAMP) "
            "FROM reading_sets"
        )
    )

    op.drop_table("reading_sets")
    op.rename_table("reading_sets_rebuilt", "reading_sets")

    op.create_index("ix_reading_sets_id", "reading_sets", ["id"])
    op.create_index("ix_reading_sets_liturgical_day_id", "reading_sets", ["liturgical_day_id"])
    op.create_index("ix_reading_sets_reading_type", "reading_sets", ["reading_type"])
    op.create_index("ix_reading_sets_selection_status", "reading_sets", ["selection_status"])


def _restore_reading_sets_table() -> None:
    """Restore the legacy ``reading_sets`` shape, reinstating the reference text.

    The reference columns are repopulated from ``reading_references`` so that a
    downgrade does not discard information that existed before the upgrade.
    """
    bind = op.get_bind()

    # Already in the legacy shape: nothing to restore.
    if "first_reading_reference" in _column_names(bind, "reading_sets"):
        return

    op.create_table(
        "reading_sets_legacy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("liturgical_day_id", sa.Integer(), nullable=False),
        sa.Column("reading_type", sa.String(length=50), nullable=False),
        sa.Column("celebration_id", sa.Integer(), nullable=True),
        sa.Column("lectionary_number", sa.String(length=50), nullable=True),
        sa.Column("first_reading_reference", sa.String(length=255), nullable=True),
        sa.Column("responsorial_psalm_reference", sa.String(length=255), nullable=True),
        sa.Column("second_reading_reference", sa.String(length=255), nullable=True),
        sa.Column("gospel_reference", sa.String(length=255), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("authority_level", sa.String(length=50), nullable=True),
        sa.Column("selection_status", sa.String(length=50), nullable=False, server_default="weekday_default"),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["liturgical_day_id"], ["liturgical_days.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["liturgical_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Reassemble the free-text columns from the structured rows, if present.
    references_available = _table_exists(bind, "reading_references")
    if references_available:
        select_references = ", ".join(
            f"COALESCE(MAX(CASE WHEN rr.reading_type = '{reading_type}' "
            f"THEN rr.display_reference END), NULL)"
            for _column, reading_type in _LEGACY_REFERENCE_COLUMNS
        )
        source = (
            "SELECT rs.id, rs.liturgical_day_id, rs.reading_type, rs.celebration_id, "
            "rs.lectionary_number, rs.source_id, rs.authority_level, "
            "rs.selection_status, rs.verification_status, rs.created_at, rs.updated_at, "
            f"{select_references} "
            "FROM reading_sets rs LEFT JOIN reading_references rr "
            "ON rr.reading_set_id = rs.id GROUP BY rs.id"
        )
        target_columns = ", ".join(column for column, _ in _LEGACY_REFERENCE_COLUMNS)
    else:
        source = (
            "SELECT id, liturgical_day_id, reading_type, celebration_id, "
            "lectionary_number, source_id, authority_level, selection_status, "
            "verification_status, created_at, updated_at, NULL, NULL, NULL, NULL "
            "FROM reading_sets"
        )
        target_columns = ", ".join(column for column, _ in _LEGACY_REFERENCE_COLUMNS)

    op.execute(
        sa.text(
            "INSERT INTO reading_sets_legacy (id, liturgical_day_id, reading_type, "
            "celebration_id, lectionary_number, source_id, authority_level, "
            "selection_status, verification_status, created_at, updated_at, "
            f"{target_columns}) {source}"
        )
    )

    op.drop_table("reading_sets")
    op.rename_table("reading_sets_legacy", "reading_sets")


def upgrade() -> None:
    # Upgrade liturgical_days table
    _upgrade_liturgical_day()

    # The reference backfill writes into reading_references, so the table has to
    # exist before reading_sets is rebuilt.
    if not _table_exists(op.get_bind(), "reading_references"):
        _create_reading_references_table()

    # Recreate reading_sets table
    _recreate_reading_sets_table()


def downgrade() -> None:
    # Restore old reading_sets table first: it reads the reference text back out
    # of reading_references, which must therefore still exist.
    _restore_reading_sets_table()

    # Drop reading_references table
    if _table_exists(op.get_bind(), "reading_references"):
        _drop_reading_references_table()

    # Downgrade liturgical_days table
    _downgrade_liturgical_day()

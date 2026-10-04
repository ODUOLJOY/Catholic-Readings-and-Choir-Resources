"""Add the country / ecclesiastical province tiers and source metadata.

Introduces the full Kenya Catholic hierarchy::

    countries -> ecclesiastical_provinces -> dioceses -> deaneries -> parishes

and records provenance (``source_url``, ``source_name``,
``source_verified_at``, ``verification_status``) on every hierarchy table.

Also relaxes ``parishes.name`` from a global unique constraint to a per-deanery
one, because many dioceses legitimately have several "St. Mary's Parish"
entries. ``parishes.diocese_id`` and ``parishes.deanery_id`` become NOT NULL
after being backfilled from the deanery.

Revision ID: 20261002_07
Revises: 20261002_06
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_07"
down_revision = "20261002_06"
branch_labels = None
depends_on = None

def _source_columns():
    """Return fresh provenance columns.

    A :class:`~sqlalchemy.Column` may only ever be attached to one ``Table``, so
    the columns cannot be a module-level constant that gets spread across
    ``dioceses``, ``deaneries`` and ``parishes``.
    """
    return (
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(length=50), nullable=False,
                  server_default="NEEDS_REVIEW"),
    )

STATUS_MAP = {
    "verified": "VERIFIED",
    "needs_review": "NEEDS_REVIEW",
    "incomplete": "INCOMPLETE",
    "VERIFIED": "VERIFIED",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
    "INCOMPLETE": "INCOMPLETE",
}


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _add_columns(table_name: str, columns) -> None:
    existing = _columns(table_name)
    with op.batch_alter_table(table_name, schema=None) as batch:
        for column in columns:
            if column.name not in existing:
                batch.add_column(column)


def _index_exists(table_name: str, index_name: str) -> bool:
    return index_name in {
        index["name"] for index in _inspector().get_indexes(table_name)
    }


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    return constraint_name in {
        constraint["name"]
        for constraint in _inspector().get_unique_constraints(table_name)
    }


def _create_unique_constraint(table_name: str, name: str, columns) -> None:
    # SQLite cannot ALTER constraints, so this always goes through batch mode.
    if not _unique_constraint_exists(table_name, name):
        with op.batch_alter_table(table_name, schema=None) as batch:
            batch.create_unique_constraint(name, list(columns))


def _create_index(table_name: str, index_name: str, columns, unique: bool = False) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, list(columns), unique=unique)


def _drop_unique_on_column(table_name: str, column_name: str) -> None:
    """Drop any UNIQUE constraint or unique index covering a single column.

    SQLite has no ``ALTER TABLE ... DROP CONSTRAINT``, so batch mode rebuilds the
    table. Two shapes must be handled:

    * a *named* constraint, which batch mode can drop directly; and
    * an *unnamed* constraint, which is what SQLAlchemy emits for a column
      declared ``unique=True``. ``drop_constraint(None)`` raises ``ValueError``,
      so in that case the table is described without the constraint and rebuilt
      from ``copy_from`` instead.
    """
    inspector = _inspector()

    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("column_names") != [column_name]:
            continue
        if constraint.get("name"):
            with op.batch_alter_table(table_name, schema=None) as batch:
                batch.drop_constraint(constraint["name"], type_="unique")
        else:
            _rebuild_without_unique(table_name, column_name)
        return

    for index in inspector.get_indexes(table_name):
        if index.get("unique") and index.get("column_names") == [column_name]:
            op.drop_index(index["name"], table_name=table_name)
            return


def _rebuild_without_unique(table_name: str, column_name: str) -> None:
    """Rebuild ``table_name`` without the unnamed UNIQUE on ``column_name``."""
    metadata = sa.MetaData()
    table = sa.Table(table_name, metadata, autoload_with=_inspector().bind)

    # ``Table.constraints`` is a plain set, so drop in place.
    for constraint in list(table.constraints):
        if (
            isinstance(constraint, sa.UniqueConstraint)
            and set(constraint.columns.keys()) == {column_name}
        ):
            table.constraints.discard(constraint)

    for column in table.columns:
        if column.name == column_name:
            column.unique = False

    with op.batch_alter_table(
        table_name, schema=None, copy_from=table, recreate="always"
    ):
        pass


def _normalise_status(table_name: str) -> None:
    """Map legacy lowercase statuses onto the canonical uppercase values."""
    bind = op.get_bind()
    for legacy, canonical in STATUS_MAP.items():
        if legacy == canonical:
            continue
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET verification_status = :canonical "
                "WHERE verification_status = :legacy"
            ).bindparams(canonical=canonical, legacy=legacy)
        )


def _count_nulls(table_name: str, column_name: str) -> int:
    return int(
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NULL"
            )
        )
        .scalar_one()
    )


def upgrade() -> None:
    if not op.get_context().as_sql:
        from app.services.migration_preflight import verify_legacy_schema

        verify_legacy_schema(op.get_bind())

    # --- countries --------------------------------------------------------
    if not _table_exists("countries"):
        op.create_table(
            "countries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=10), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("source_name", sa.String(length=255), nullable=True),
            sa.Column("source_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verification_status", sa.String(length=50), nullable=False,
                      server_default="NEEDS_REVIEW"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_countries_name"),
            sa.UniqueConstraint("code", name="uq_countries_code"),
        )
        _create_index("countries", "ix_countries_code", ("code",))

    # Seed the single country this application serves. Without this row the
    # ``parishes.country_id`` backfill below would silently match nothing.
    _seed_kenya()

    # --- ecclesiastical provinces ----------------------------------------
    if not _table_exists("ecclesiastical_provinces"):
        op.create_table(
            "ecclesiastical_provinces",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("short_name", sa.String(length=100), nullable=True),
            sa.Column("country_id", sa.Integer(), nullable=False),
            sa.Column("metropolitan_archdiocese_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("source_name", sa.String(length=255), nullable=True),
            sa.Column("source_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verification_status", sa.String(length=50), nullable=False,
                      server_default="NEEDS_REVIEW"),
            sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
            sa.ForeignKeyConstraint(["metropolitan_archdiocese_id"], ["dioceses.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_provinces_name"),
            sa.UniqueConstraint("code", name="uq_provinces_code"),
        )
        _create_index("ecclesiastical_provinces", "ix_ecclesiastical_provinces_code", ("code",))
        _create_index("ecclesiastical_provinces", "ix_ecclesiastical_provinces_country_id", ("country_id",))

    # --- dioceses ---------------------------------------------------------
    _add_columns(
        "dioceses",
        (
            sa.Column("short_name", sa.String(length=100), nullable=True),
            sa.Column("is_archdiocese", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("is_military_ordinariate", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("erected_on", sa.String(length=50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column("ecclesiastical_province_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            *_source_columns(),
        ),
    )
    _create_foreign_key(
        "fk_dioceses_ecclesiastical_province",
        "dioceses",
        "ecclesiastical_province_id",
        "ecclesiastical_provinces",
    )
    _create_index("dioceses", "ix_dioceses_ecclesiastical_province_id", ("ecclesiastical_province_id",))
    _normalise_status("dioceses")

    # --- deaneries --------------------------------------------------------
    _add_columns(
        "deaneries",
        (
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            *_source_columns(),
        ),
    )
    _normalise_status("deaneries")

    # --- parishes ---------------------------------------------------------
    _add_columns(
        "parishes",
        (
            sa.Column("country_id", sa.Integer(), nullable=True),
            *_source_columns(),
        ),
    )
    _create_foreign_key("fk_parishes_country", "parishes", "country_id", "countries")
    _create_index("parishes", "ix_parishes_country_id", ("country_id",))

    _normalise_status("parishes")

    # Parishes are unique within a deanery, not globally.
    _drop_unique_on_column("parishes", "name")
    _create_index("parishes", "ix_parishes_name", ("name",))

    # Backfill the denormalised diocese and country before enforcing NOT NULL.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE parishes SET diocese_id = ("
            "  SELECT deaneries.diocese_id FROM deaneries"
            "  WHERE deaneries.id = parishes.deanery_id"
            ") WHERE diocese_id IS NULL AND deanery_id IS NOT NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE parishes SET country = 'Kenya' WHERE country IS NULL"
        )
    )
    if _table_exists("countries"):
        bind.execute(
            sa.text(
                "UPDATE parishes SET country_id = ("
                "  SELECT countries.id FROM countries WHERE countries.code = 'KE'"
                ") WHERE country_id IS NULL"
            )
        )

    for column in ("deanery_id", "diocese_id"):
        if _count_nulls("parishes", column):
            raise RuntimeError(
                f"Cannot enforce parishes.{column} NOT NULL while rows have no "
                "deanery or diocese. Reassign or deactivate those parishes first."
            )

    with op.batch_alter_table("parishes") as batch:
        batch.alter_column("deanery_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.alter_column("diocese_id", existing_type=sa.Integer(),
                           nullable=False)

    _create_unique_constraint("parishes", "uq_parishes_deanery_name",
                              ("deanery_id", "name"))

    if not _duplicates("deaneries", ("diocese_id", "name")):
        _create_unique_constraint("deaneries", "uq_deaneries_diocese_name",
                                  ("diocese_id", "name"))
    if not _duplicates("dioceses", ("name",)):
        _create_unique_constraint("dioceses", "uq_dioceses_name", ("name",))


def _seed_kenya() -> None:
    """Insert the Kenya country row if it is not already present."""
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM countries WHERE code = :code"),
        {"code": "KE"},
    ).first()
    if existing:
        return
    bind.execute(
        sa.text(
            "INSERT INTO countries "
            "(name, code, is_active, verification_status) "
            "VALUES (:name, :code, :is_active, :verification_status)"
        ),
        {
            "name": "Kenya",
            "code": "KE",
            "is_active": True,
            "verification_status": "VERIFIED",
        },
    )


def _create_foreign_key(name: str, table: str, column: str, target: str) -> None:
    """Add a foreign key, skipping it when it is already present."""
    if _foreign_key_exists(table, name, column, target):
        return
    with op.batch_alter_table(table, schema=None) as batch:
        batch.create_foreign_key(name, target, [column], ["id"])


def _foreign_key_exists(table: str, name: str, column: str, target: str) -> bool:
    for foreign_key in _inspector().get_foreign_keys(table):
        if (
            foreign_key.get("name") == name
            and foreign_key.get("referred_table") == target
            and list(foreign_key.get("constrained_columns") or []) == [column]
        ):
            return True
    return False


def _duplicates(table_name: str, columns) -> bool:
    joined = ", ".join(columns)
    row = op.get_bind().execute(
        sa.text(
            f"SELECT 1 FROM {table_name} GROUP BY {joined} "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    return row is not None


def downgrade() -> None:
    # Constraint changes and NOT NULL relaxation go through batch mode so this
    # also works on SQLite.
    if _unique_constraint_exists("parishes", "uq_parishes_deanery_name"):
        with op.batch_alter_table("parishes", schema=None) as batch:
            batch.drop_constraint("uq_parishes_deanery_name", type_="unique")
    if _unique_constraint_exists("deaneries", "uq_deaneries_diocese_name"):
        with op.batch_alter_table("deaneries", schema=None) as batch:
            batch.drop_constraint("uq_deaneries_diocese_name", type_="unique")
    if _unique_constraint_exists("dioceses", "uq_dioceses_name"):
        with op.batch_alter_table("dioceses", schema=None) as batch:
            batch.drop_constraint("uq_dioceses_name", type_="unique")

    # Restore the legacy global unique on parishes.name.
    if not _duplicates("parishes", ("name",)):
        _create_unique_constraint("parishes", "uq_parishes_name", ("name",))

    for column in ("deanery_id", "diocese_id"):
        with op.batch_alter_table("parishes", schema=None) as batch:
            batch.alter_column(column, existing_type=sa.Integer(), nullable=True)

    # Indexes first: a SQLite index outlives the column it references otherwise.
    _drop_index_if_exists("parishes", "ix_parishes_country_id")
    _drop_index_if_exists("parishes", "ix_parishes_name")
    _drop_index_if_exists("dioceses", "ix_dioceses_ecclesiastical_province_id")
    _drop_index_if_exists(
        "ecclesiastical_provinces", "ix_ecclesiastical_provinces_country_id"
    )
    _drop_index_if_exists(
        "ecclesiastical_provinces", "ix_ecclesiastical_provinces_code"
    )
    _drop_index_if_exists("countries", "ix_countries_code")

    # ``verification_status`` already existed on deaneries and parishes, so it is
    # mapped back to the legacy lowercase values rather than dropped. It is a
    # new column on dioceses, so there it is removed.
    for table_name in ("deaneries", "parishes"):
        _restore_legacy_status(table_name)
    for column in ("source_url", "source_name", "source_verified_at"):
        for table_name in ("parishes", "deaneries", "dioceses"):
            _drop_column(table_name, column)
    _drop_column("dioceses", "verification_status")
    _drop_column("parishes", "country_id")

    if _table_exists("ecclesiastical_provinces"):
        op.drop_table("ecclesiastical_provinces")
    if _table_exists("countries"):
        op.drop_table("countries")


def _source_column_names():
    return ("source_url", "source_name", "source_verified_at", "verification_status")


def _restore_legacy_status(table_name: str) -> None:
    """Map the canonical uppercase statuses back onto legacy lowercase values."""
    if not _table_exists(table_name) or "verification_status" not in _columns(table_name):
        return
    bind = op.get_bind()
    for canonical, legacy in (("VERIFIED", "verified"),
                              ("NEEDS_REVIEW", "needs_review"),
                              ("INCOMPLETE", "incomplete")):
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET verification_status = :legacy "
                "WHERE verification_status = :canonical"
            ).bindparams(canonical=canonical, legacy=legacy)
        )


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _table_exists(table_name) and _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column(table_name: str, column_name: str) -> None:
    if not _table_exists(table_name):
        return
    if column_name not in _columns(table_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch:
        batch.drop_column(column_name)
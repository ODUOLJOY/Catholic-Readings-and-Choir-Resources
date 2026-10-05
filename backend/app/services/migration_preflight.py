from sqlalchemy import inspect
from sqlalchemy.engine import Connection


REQUIRED_LEGACY_COLUMNS = {
    "users": {"id", "parish_id"},
    "dioceses": {"id"},
    "deaneries": {"id", "diocese_id"},
    "parishes": {"id", "diocese_id", "deanery_id"},
    "readings": {"id", "reading_date", "language"},
    "choir_resources": {"id"},
}


def missing_legacy_schema(connection: Connection) -> list[str]:
    """Return the absent legacy tables/columns, or ``[]`` when the schema is present.

    Split out from :func:`verify_legacy_schema` so the baseline bootstrap can ask
    "is anything missing?" without the raising behaviour.
    """
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    missing: list[str] = []
    for table_name, required_columns in REQUIRED_LEGACY_COLUMNS.items():
        if table_name not in existing_tables:
            missing.append(f"{table_name} (table missing)")
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing.extend(
            f"{table_name}.{column}"
            for column in sorted(required_columns - existing_columns)
        )
    return missing


def verify_legacy_schema(connection: Connection) -> None:
    missing = missing_legacy_schema(connection)
    if missing:
        raise RuntimeError(
            "Migration preflight failed; expected the existing application "
            "schema before applying additive migrations. Missing: "
            + ", ".join(missing)
        )

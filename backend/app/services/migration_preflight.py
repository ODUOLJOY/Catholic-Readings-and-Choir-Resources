from sqlalchemy import inspect
from sqlalchemy.engine import Connection


REQUIRED_LEGACY_COLUMNS = {
    "users": {"id", "parish_id"},
    "dioceses": {"id"},
    "deaneries": {"id", "diocese_id"},
    "parishes": {"id", "diocese_id", "deanery_id"},
    "choir_resources": {"id"},
}


def verify_legacy_schema(connection: Connection) -> None:
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
    if missing:
        raise RuntimeError(
            "Migration preflight failed; expected the existing application "
            "schema before applying additive migrations. Missing: "
            + ", ".join(missing)
        )

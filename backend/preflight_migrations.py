from app.db.database import engine
from app.services.migration_preflight import verify_legacy_schema


def main() -> None:
    with engine.connect() as connection:
        verify_legacy_schema(connection)
    print("Migration preflight passed: required legacy tables and columns exist.")


if __name__ == "__main__":
    main()

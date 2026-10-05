"""Idempotent database schema bootstrap for deployments.

Why this exists
---------------
Every Alembic revision in this repository is *additive*: each one starts by
asserting the original application tables already exist (see
``app.services.migration_preflight``), and none of them create them. The only
code that ever created those tables was ``init_db()``, which runs solely when
``AUTO_CREATE_TABLES`` is true -- and that flag is ``false`` in production
(``backend/render.yaml``). No deployment ran ``alembic upgrade head`` either.

The result was an environment whose database had no application schema at all,
so every table-backed route raised at request time and returned HTTP 500. The
browser then reported those failures as CORS errors, because an unhandled 500
never passes through ``CORSMiddleware`` and therefore carries no
``Access-Control-Allow-Origin`` header.

What this does
--------------
``bootstrap_schema()`` picks the only two correct actions for the database it is
given, and refuses to guess in every other case:

* **No application tables at all** -- create the current schema from the model
  metadata and ``alembic stamp head``. The models already describe the end state
  of every historical migration, so replaying the chain would be redundant and
  the revision marker must be stamped rather than replayed.
* **An existing schema** -- run ``alembic upgrade head`` exactly as before.

Anything in between (a partially provisioned database, or a schema missing a
column the preflight requires) is reported as an error rather than being
"repaired", because overlaying a baseline onto a half-created schema is the one
case where guessing silently destroys data.

Run it with::

    python -m app.services.schema_bootstrap
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class SchemaBootstrapError(RuntimeError):
    """Raised when the database cannot be bootstrapped safely."""


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


def _application_tables(connection) -> set[str]:
    names = set(inspect(connection).get_table_names())
    # ``alembic_version`` is Alembic bookkeeping, not application schema.
    return names - {"alembic_version"}


def _create_current_schema(connection) -> None:
    # Importing the package registers every table on the shared metadata.
    import app.models  # noqa: F401
    from app.db.database import Base

    Base.metadata.create_all(bind=connection, checkfirst=True)


def check_schema() -> str:
    """Validate the configured database without changing it.

    This is the read-only counterpart to :func:`bootstrap_schema` and is what the
    production start command runs. Application startup must not mutate the
    production schema: an automatic ``create_all`` on boot is an unreviewed
    migration that runs on every deploy, and on a partially provisioned database
    it can silently produce a schema nobody approved. Startup therefore reports
    what is wrong and exits, and provisioning happens as a deliberate, separately
    approved step via ``python -m app.services.schema_bootstrap``.

    Returns an action name describing the current state; raises
    :class:`SchemaBootstrapError` when the database cannot serve traffic.
    """
    from app.db.database import engine
    from app.services.migration_preflight import missing_legacy_schema

    with engine.connect() as connection:
        tables = _application_tables(connection)
        if not tables:
            raise SchemaBootstrapError(
                "No application schema found. Provision the database explicitly "
                "before starting the service: "
                "python -m app.services.schema_bootstrap"
            )
        missing = missing_legacy_schema(connection)
        if missing:
            raise SchemaBootstrapError(
                "Database is partially provisioned. Missing: " + ", ".join(missing)
            )
        return "ready"


def bootstrap_schema() -> str:
    """Bring the configured database to the current schema. Returns an action name.

    Both branches are idempotent, so this is safe to re-run. It is **not** part of
    application startup -- see :func:`check_schema` -- because provisioning the
    production schema has to be an explicit, reviewed action.
    """
    from app.db.database import engine
    from app.services.migration_preflight import missing_legacy_schema

    cfg = _alembic_config()

    with engine.connect() as connection:
        tables = _application_tables(connection)
        if not tables:
            logger.info("No application schema found; creating it from the models.")
            _create_current_schema(connection)
            connection.commit()
            action = "created-and-stamped"
        else:
            missing = missing_legacy_schema(connection)
            if missing:
                raise SchemaBootstrapError(
                    "Refusing to bootstrap: the database is partially provisioned. "
                    "Missing: " + ", ".join(missing)
                )
            action = "upgraded"

    # The version marker is written by Alembic on its own connection.
    if action == "created-and-stamped":
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")

    logger.info("Schema bootstrap complete (%s).", action)
    return action


def main() -> int:
    """Entry point for the explicit provisioning command.

    ``--check`` runs the read-only startup validation instead of provisioning.
    """
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    check_only = "--check" in sys.argv[1:]
    try:
        action = check_schema() if check_only else bootstrap_schema()
    except SchemaBootstrapError as exc:
        logger.error("%s", exc)
        return 1
    print(f"schema {'check' if check_only else 'bootstrap'}: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
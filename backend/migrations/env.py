from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Import models so Alembic can compare the complete declared schema.
import app.models.auth  # noqa: E402,F401
import app.models.community  # noqa: E402,F401
import app.models.content  # noqa: E402,F401
import app.models.download  # noqa: E402,F401
import app.models.favorite  # noqa: E402,F401
import app.models.liturgical  # noqa: E402,F401
import app.models.notification  # noqa: E402,F401
import app.models.parish  # noqa: E402,F401
import app.models.parish_request  # noqa: E402,F401
import app.models.payment  # noqa: E402,F401
import app.models.readings  # noqa: E402,F401
import app.models.report  # noqa: E402,F401
import app.models.saint  # noqa: E402,F401
import app.models.user  # noqa: E402,F401
import app.models.choir  # noqa: E402,F401
import app.models.locations  # noqa: E402,F401
from app.db.database import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


DATABASE_URL = settings.DATABASE_URL


database_url = make_url(DATABASE_URL)
engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "future": True,
}
if database_url.get_backend_name() == "sqlite":
    if database_url.database in (None, "", ":memory:"):
        engine_options.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
elif database_url.get_backend_name() != "sqlite":
    engine_options.update(pool_size=20, max_overflow=30)

engine = create_engine(DATABASE_URL, **engine_options)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
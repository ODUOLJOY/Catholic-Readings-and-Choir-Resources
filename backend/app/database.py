from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    future=True,
)

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


def init_db():
    """
    Creates all database tables.

    Call once during application startup.
    """
    import app.models.user
    import app.models.parish
    import app.models.readings
    import app.models.payment
    import app.models.saint
    import app.models.choir
    import app.models.download
    import app.models.notification
    import app.models.report
    import app.models.favorite

    Base.metadata.create_all(bind=engine)
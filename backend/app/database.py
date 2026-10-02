from app.core.config import settings
from app.db.database import Base, SessionLocal, engine, get_db

DATABASE_URL = settings.DATABASE_URL


def init_db():
    """
    Creates all database tables.

    Call once during application startup.
    """
    import app.models.user
    import app.models.auth
    import app.models.locations
    import app.models.parish
    import app.models.readings
    import app.models.payment
    import app.models.saint
    import app.models.choir
    import app.models.download
    import app.models.notification
    import app.models.parish_request
    import app.models.report
    import app.models.favorite
    import app.models.liturgical
    import app.models.community

    # Ensure all tables are created
    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "DATABASE_URL", "SessionLocal", "engine", "get_db", "init_db"]
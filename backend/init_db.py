from app.database import Base, engine

# Import all models so SQLAlchemy registers them
import app.models.user
import app.models.parish
import app.models.readings

try:
    import app.models.saint
except ImportError:
    pass

try:
    import app.models.choir
except ImportError:
    pass

try:
    import app.models.favorite
except ImportError:
    pass

try:
    import app.models.download
except ImportError:
    pass

try:
    import app.models.notification
except ImportError:
    pass

try:
    import app.models.report
except ImportError:
    pass


def init_db():
    """
    Create all database tables.
    """
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
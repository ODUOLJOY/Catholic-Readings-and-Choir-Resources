from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)


def test_connection() -> bool:
    """
    Test PostgreSQL connection.
    """

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    except SQLAlchemyError as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    if test_connection():
        print("Database connected successfully.")
    else:
        print("Database connection failed.")
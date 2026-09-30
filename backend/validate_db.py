from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

def validate_db():
    print("--- Database Configuration Validation ---")
    url = make_url(settings.DATABASE_URL)
    
    print(f"Host: {url.host}")
    print(f"Port: {url.port}")
    print(f"Database: {url.database}")
    print(f"User: {url.username}")
    
    # Do NOT print password
    
    print("\n--- Connection Test ---")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print("SUCCESS: Connection established and SELECT 1 executed.")
    except Exception as e:
        print(f"FAILURE: Could not connect to database.")
        print(f"Error: {e}")

if __name__ == "__main__":
    validate_db()

import sqlalchemy
from app.db.database import engine

print("Adding verification_status and is_active columns...")
with engine.connect() as conn:
    try:
        # Deanery
        conn.execute(sqlalchemy.text("ALTER TABLE deaneries ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
        conn.execute(sqlalchemy.text("ALTER TABLE deaneries ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50) DEFAULT 'needs_review'"))
        # ParishRequest
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS parish_requests (
                id SERIAL PRIMARY KEY,
                parish_name VARCHAR(255) NOT NULL,
                jurisdiction_name VARCHAR(255),
                deanery_name VARCHAR(255),
                town VARCHAR(150),
                details TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                submitted_by_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        print("Columns added successfully.")
    except Exception as e:
        print(f"Error: {e}")

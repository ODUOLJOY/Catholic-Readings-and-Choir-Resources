import sqlalchemy
from app.db.database import engine

print("Dropping redundant columns from parishes table...")
with engine.connect() as conn:
    try:
        conn.execute(sqlalchemy.text("ALTER TABLE parishes DROP COLUMN IF EXISTS diocese"))
        conn.execute(sqlalchemy.text("ALTER TABLE parishes DROP COLUMN IF EXISTS archdiocese"))
        conn.commit()
        print("Redundant columns dropped.")
    except Exception as e:
        print(f"Error dropping columns: {e}")

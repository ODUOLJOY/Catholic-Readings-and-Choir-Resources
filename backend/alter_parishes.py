import sqlalchemy
from app.db.database import engine

print("Altering parishes table...")
with engine.connect() as conn:
    conn.execute(sqlalchemy.text("ALTER TABLE parishes ADD COLUMN IF NOT EXISTS deanery_id INTEGER"))
    conn.execute(sqlalchemy.text("ALTER TABLE parishes ADD COLUMN IF NOT EXISTS diocese_id INTEGER"))
    conn.commit()
print("Table altered.")

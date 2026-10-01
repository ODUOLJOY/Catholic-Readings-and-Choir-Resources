import sqlalchemy
from sqlalchemy import Column, String
from app.db.database import engine

print("Adding code column to parishes...")
with engine.connect() as conn:
    conn.execute(sqlalchemy.text("ALTER TABLE parishes ADD COLUMN IF NOT EXISTS code VARCHAR(50) UNIQUE DEFAULT 'tmp'"))
    conn.commit()
print("Column added.")

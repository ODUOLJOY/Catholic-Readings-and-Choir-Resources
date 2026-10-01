import sqlalchemy
from app.db.database import engine

print("Altering favorites table...")
with engine.connect() as conn:
    # Add new columns
    conn.execute(sqlalchemy.text("ALTER TABLE favorites ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50)"))
    conn.execute(sqlalchemy.text("ALTER TABLE favorites ADD COLUMN IF NOT EXISTS target_resource_id INTEGER"))
    conn.execute(sqlalchemy.text("ALTER TABLE favorites ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"))
    
    # Optionally update existing rows if they had reading_id or resource_id
    # This is a safe way to migrate without dropping columns.
    # conn.execute(sqlalchemy.text("UPDATE favorites SET resource_type = 'reading', target_resource_id = reading_id WHERE reading_id IS NOT NULL"))
    # conn.execute(sqlalchemy.text("UPDATE favorites SET resource_type = 'choir', target_resource_id = resource_id WHERE resource_id IS NOT NULL"))

    conn.commit()
print("Table altered.")

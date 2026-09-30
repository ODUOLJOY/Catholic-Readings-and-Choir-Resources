import json
import sys
from datetime import date
from sqlalchemy.orm import sessionmaker
from app.db.database import engine
from app.services.liturgical_sync import LiturgicalSyncService

def import_bulk(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    stats = {"total": len(data), "created": 0, "updated": 0, "errors": 0}
    
    for entry in data:
        # Convert date string to date object
        try:
            entry['date'] = date.fromisoformat(entry['date'])
            LiturgicalSyncService.import_verified_data(db, entry)
            stats["created"] += 1
        except Exception as e:
            print(f"Error importing {entry.get('date')}: {e}")
            stats["errors"] += 1
            
    db.commit()
    db.close()
    print(f"Import complete: {stats}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_bulk_2026.py <json_file>")
    else:
        import_bulk(sys.argv[1])

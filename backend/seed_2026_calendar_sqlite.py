"""
Seed 2026 Kenya calendar data from the calendar engine using SQLite.

This script populates a local SQLite database with calculated liturgical calendar data
for 2026. The data is marked as "unverified" since it's calculated rather than
imported from an authoritative source.

Usage:
    python seed_2026_calendar_sqlite.py
"""
import os
import sys
from datetime import date, timedelta

# Force SQLite for this script
os.environ["DATABASE_URL"] = "sqlite:///test_2026.db"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.services.liturgical_sync import LiturgicalSyncService
from app.services.calendar import get_calendar_info


def seed_2026():
    """Seed 2026 calendar data from the calendar engine."""
    # Create SQLite engine
    engine = create_engine("sqlite:///test_2026.db", echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session = sessionmaker(bind=engine)()
    
    start_date = date(2026, 1, 1)
    end_date = date(2026, 12, 31)
    
    stats = {
        "total": 0,
        "created": 0,
        "errors": 0,
    }
    
    target_date = start_date
    while target_date <= end_date:
        try:
            # Calculate calendar info
            calendar_info = get_calendar_info(target_date, "KE")
            
            # Convert to import format
            import_data = {
                "date": calendar_info["date"],
                "region": calendar_info["region"],
                "celebration": calendar_info["celebration"],
                "rank": calendar_info["rank"],
                "liturgical_color": calendar_info["color"],
                "sunday_cycle": calendar_info["sunday_cycle"],
                "weekday_cycle": calendar_info["weekday_cycle"],
                "season": calendar_info["season"],
                "week": calendar_info["week"],
                "source": "Calendar Engine (Calculated)",
                "verification_status": "unverified",  # Calculated, not verified
            }
            
            # Import using sync service
            LiturgicalSyncService.import_verified_data(session, import_data)
            stats["created"] += 1
            
            if stats["total"] % 30 == 0:
                print(f"Processed {stats['total']} dates...")
                session.commit()
            
        except Exception as e:
            print(f"Error processing {target_date}: {e}")
            stats["errors"] += 1
        
        stats["total"] += 1
        target_date += timedelta(days=1)
    
    session.commit()
    session.close()
    
    print(f"\nSeeding complete for 2026:")
    print(f"  Total dates: {stats['total']}")
    print(f"  Created: {stats['created']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Database: test_2026.db")
    
    return stats


if __name__ == "__main__":
    seed_2026()

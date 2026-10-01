import requests
from datetime import date
from sqlalchemy.orm import Session
from app.models.liturgical import LiturgicalDay, LiturgicalSource, ReadingSet
from app.services.calendar import get_calendar_info

class LiturgicalSyncService:
    @staticmethod
    def sync_date(db: Session, target_date: date):
        # 1. Check if data already exists
        existing = db.query(LiturgicalDay).filter(LiturgicalDay.date == target_date).first()
        if existing:
            return existing
        
        # 2. Fetch data (simplified implementation for structure)
        # In a real production system, this would fetch from a reliable source or API
        # For now, we will calculate what we can and mark it for manual review if needed.
        calendar_info = get_calendar_info(target_date)
        
        # Create LiturgicalDay
        day = LiturgicalDay(
            date=target_date,
            liturgical_year=calendar_info["liturgical_year"],
            season=calendar_info["season"],
            celebration_name=calendar_info["celebration"],
            celebration_rank=calendar_info["rank"],
            liturgical_color=calendar_info["color"],
        )
        
        db.add(day)
        db.commit()
        db.refresh(day)
        
        return day
    
    @staticmethod
    def sync_range(db: Session, start_date: date, end_date: date):
        # Implement range sync
        pass
    
    @staticmethod
    def import_verified_data(db: Session, data: dict):
        # 1. Validate data
        
        # 2. Upsert
        day = db.query(LiturgicalDay).filter(LiturgicalDay.date == data["date"]).first()
        if not day:
            day = LiturgicalDay(date=data["date"])
            db.add(day)
        
        day.celebration_name = data["celebration"]
        day.celebration_rank = data["rank"]
        day.liturgical_color = data["liturgical_color"]
        day.liturgical_year = data["liturgical_year"]
        day.season = data["season"]
        day.verification_status = "verified"
        
        # Resolve or create source
        source = db.query(LiturgicalSource).filter(LiturgicalSource.name == data.get("source")).first()
        if not source:
            source = LiturgicalSource(
                name=data.get("source"),
                source_type="manual_import",
                authority_level="secondary_reference"
            )
            db.add(source)
            db.commit()
            db.refresh(source)
        day.source_id = source.id
        
        # Handle reading_sets
        if "reading_sets" in data:
            for rs_data in data["reading_sets"]:
                # Check for existing reading set of this type for this day
                rs = db.query(ReadingSet).filter(
                    ReadingSet.liturgical_day_id == day.id,
                    ReadingSet.reading_type == rs_data["type"]
                ).first()
                if not rs:
                    rs = ReadingSet(liturgical_day_id=day.id, reading_type=rs_data["type"])
                    db.add(rs)
                
                rs.lectionary_number = rs_data.get("lectionary_number")
                rs.first_reading_reference = rs_data.get("first_reading")
                rs.responsorial_psalm_reference = rs_data.get("psalm")
                rs.second_reading_reference = rs_data.get("second_reading")
                rs.gospel_reference = rs_data.get("gospel")
                rs.selection_status = rs_data.get("selection_status", "weekday_default")
                rs.source_id = source.id
        
        db.commit()
        db.refresh(day)
        
        return day

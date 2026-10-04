import requests
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
from app.models.liturgical import LiturgicalDay, LiturgicalSource
from app.models.reading_reference import ReadingSet, ReadingReference
from app.services.calendar import get_calendar_info

class LiturgicalSyncService:
    @staticmethod
    def sync_date(db: Session, target_date: date, region: str = "KE"):
        """Sync a single date from calendar engine (for initial data population)."""
        # 1. Check if data already exists
        existing = db.query(LiturgicalDay).filter(
            LiturgicalDay.date == target_date,
            LiturgicalDay.region == region
        ).first()
        if existing:
            return existing
        
        # 2. Calculate from calendar engine
        calendar_info = get_calendar_info(target_date, region)
        
        # Create LiturgicalDay
        day = LiturgicalDay(
            date=target_date,
            sunday_cycle=calendar_info["sunday_cycle"],
            weekday_cycle=calendar_info["weekday_cycle"],
            season=calendar_info["season"],
            week_number=calendar_info["week"],
            celebration_name=calendar_info["celebration"],
            celebration_rank=calendar_info["rank"],
            liturgical_color=calendar_info["color"],
            region=region,
            verification_status="unverified",  # Calculated, not verified
        )
        
        db.add(day)
        db.commit()
        db.refresh(day)
        
        return day
    
    @staticmethod
    def sync_range(db: Session, start_date: date, end_date: date, region: str = "KE"):
        """Sync a date range from calendar engine."""
        stats = {"total": 0, "created": 0, "updated": 0, "errors": 0}
        
        target_date = start_date
        while target_date <= end_date:
            try:
                LiturgicalSyncService.sync_date(db, target_date, region)
                stats["created"] += 1
            except Exception as e:
                print(f"Error syncing {target_date}: {e}")
                stats["errors"] += 1
            stats["total"] += 1
            target_date += timedelta(days=1)
        
        db.commit()
        return stats
    
    @staticmethod
    def import_verified_data(db: Session, data: dict):
        """Import verified liturgical data with structured reading references."""
        from datetime import datetime
        
        # 1. Convert date string to date object if needed
        if isinstance(data["date"], str):
            target_date = date.fromisoformat(data["date"])
        else:
            target_date = data["date"]
        
        # 2. Upsert LiturgicalDay
        day = db.query(LiturgicalDay).filter(
            LiturgicalDay.date == target_date,
            LiturgicalDay.region == data.get("region", "KE")
        ).first()
        
        if not day:
            day = LiturgicalDay(
                date=target_date,
                region=data.get("region", "KE")
            )
            db.add(day)
        
        # Update liturgical data
        day.sunday_cycle = data.get("sunday_cycle")
        day.weekday_cycle = data.get("weekday_cycle")
        day.season = data.get("season")
        day.week_number = data.get("week")
        day.celebration_name = data["celebration"]
        day.celebration_rank = data["rank"]
        day.liturgical_color = data["liturgical_color"]
        day.verification_status = "verified"
        day.last_verified_at = datetime.utcnow()
        
        # Resolve or create source
        source_name = data.get("source", "Universalis")
        source = db.query(LiturgicalSource).filter(LiturgicalSource.name == source_name).first()
        if not source:
            source = LiturgicalSource(
                name=source_name,
                source_type="external_api",
                country=data.get("region", "KE"),
                authority_level="primary_reference"
            )
            db.add(source)
            db.commit()
            db.refresh(source)
        day.source_id = source.id
        day.source_record_id = data.get("source_record_id")
        
        # Handle reading_sets with structured references
        if "reading_sets" in data:
            for rs_data in data["reading_sets"]:
                # Check for existing reading set of this type and status for this day
                rs = db.query(ReadingSet).filter(
                    ReadingSet.liturgical_day_id == day.id,
                    ReadingSet.reading_type == rs_data.get("type"),
                    ReadingSet.selection_status == rs_data.get("selection_status", "weekday_default")
                ).first()
                
                if not rs:
                    rs = ReadingSet(
                        liturgical_day_id=day.id,
                        reading_type=rs_data.get("type"),
                        selection_status=rs_data.get("selection_status", "weekday_default")
                    )
                    db.add(rs)
                    db.flush()  # Flush to get the ID before adding references
                
                rs.celebration_name = rs_data.get("celebration_name")
                rs.lectionary_number = rs_data.get("lectionary_number")
                rs.authority_level = rs_data.get("authority_level")
                rs.verification_status = "verified"
                rs.verified_at = datetime.utcnow()
                rs.source_id = source.id
                
                # Handle structured reading references
                if "readings" in rs_data:
                    # Delete old references for this set
                    for old_ref in rs.reading_references:
                        db.delete(old_ref)
                    
                    # Add new references
                    for ref_data in rs_data["readings"]:
                        ref = ReadingReference(
                            reading_set_id=rs.id,
                            reading_type=ref_data.get("type"),
                            book=ref_data.get("book"),
                            chapter_start=ref_data.get("chapter_start"),
                            verse_start=ref_data.get("verse_start"),
                            chapter_end=ref_data.get("chapter_end"),
                            verse_end=ref_data.get("verse_end"),
                            display_reference=ref_data.get("display_reference"),
                            psalm_number_variant=ref_data.get("psalm_number_variant"),
                            sequence=ref_data.get("sequence", 0),
                            is_alternative=ref_data.get("is_alternative", False),
                            is_optional=ref_data.get("is_optional", False),
                            is_primary=ref_data.get("is_primary", True),
                            lectionary_number=ref_data.get("lectionary_number"),
                            comment=ref_data.get("comment")
                        )
                        db.add(ref)
        
        db.commit()
        db.refresh(day)
        
        return day

from datetime import date
from sqlalchemy.orm import Session

from app.models.readings import Reading
from app.services.calendar import get_calendar_info
from app.services.liturgical_sync import LiturgicalSyncService


class MissalEngine:
    """
    Catholic Missal Engine.

    This service powers the Daily Readings API and is designed
    so that future synchronization with official Catholic
    lectionary providers can be added without changing the
    frontend.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # DAILY READINGS
    # ==========================================

    @staticmethod
    def sync_today(db: Session):
        return LiturgicalSyncService.sync_date(db, date.today())

    def get_today_readings(self):
        return self.get_readings(date.today())

    def _select_reading_set(self, day):
        sets = day.reading_sets
        if not sets:
            return None
        
        # Categorize available sets
        by_status = {rs.selection_status: rs for rs in sets}
        
        rank = day.celebration_rank.lower()
        
        if rank in ["solemnity", "feast"]:
            return by_status.get("strictly_proper") or by_status.get("proper") or sets[0]
            
        elif "memorial" in rank:
            # Memorials use strictly proper if available, otherwise default to daily/weekday
            if "strictly_proper" in by_status:
                return by_status["strictly_proper"]
            return by_status.get("weekday_default") or sets[0]
            
        else: # Weekday/Other
            return by_status.get("weekday_default") or sets[0]

    def get_readings(self, reading_date: date):
        from app.models.liturgical import LiturgicalDay, ReadingSet

        # 1. Try to get verified LiturgicalDay
        day = self.db.query(LiturgicalDay).filter(LiturgicalDay.date == reading_date).first()
        
        # 2. Get Reading content (if exists)
        reading = (
            self.db.query(Reading)
            .filter(
                Reading.reading_date == reading_date,
                Reading.published == True,
            )
            .first()
        )

        # 3. Merge calendar info
        calendar_info = get_calendar_info(reading_date)
        
        if day:
            selected = self._select_reading_set(day)
            
            calendar_info.update({
                "celebration": day.celebration_name,
                "rank": day.celebration_rank,
                "color": day.liturgical_color,
                "selected_reading_set": {
                    "type": selected.reading_type,
                    "lectionary_number": selected.lectionary_number,
                    "first_reading": selected.first_reading_reference,
                    "psalm": selected.responsorial_psalm_reference,
                    "second_reading": selected.second_reading_reference,
                    "gospel": selected.gospel_reference,
                    "source": selected.source.name if selected.source else None,
                    "verification_status": selected.verification_status,
                } if selected else None,
                "available_reading_sets": [
                    {
                        "type": rs.reading_type,
                        "lectionary_number": rs.lectionary_number,
                        "first_reading": rs.first_reading_reference,
                        "psalm": rs.responsorial_psalm_reference,
                        "second_reading": rs.second_reading_reference,
                        "gospel": rs.gospel_reference,
                        "source": rs.source.name if rs.source else None,
                        "verification_status": rs.verification_status,
                    } for rs in day.reading_sets
                ]
            })

        return {
            "date": reading_date,
            "calendar": calendar_info,
            "reading": reading,
        }

    # ==========================================
    # SEARCH
    # ==========================================

    def search(self, query: str):

        return (
            self.db.query(Reading)
            .filter(
                (Reading.feast.ilike(f"%{query}%"))
                | (Reading.saint.ilike(f"%{query}%"))
                | (Reading.first_reading.ilike(f"%{query}%"))
                | (Reading.psalm.ilike(f"%{query}%"))
                | (Reading.second_reading.ilike(f"%{query}%"))
                | (Reading.gospel.ilike(f"%{query}%"))
                | (Reading.reflection.ilike(f"%{query}%"))
            )
            .all()
        )

    # ==========================================
    # FILTERS
    # ==========================================

    def by_season(self, season: str):

        return (
            self.db.query(Reading)
            .filter(
                Reading.liturgical_season == season,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.asc())
            .all()
        )

    def by_year(self, year: str):

        return (
            self.db.query(Reading)
            .filter(
                Reading.liturgical_year == year,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.asc())
            .all()
        )

    def by_language(self, language: str):

        return (
            self.db.query(Reading)
            .filter(
                Reading.language == language,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.asc())
            .all()
        )

    # ==========================================
    # DATE RANGE
    # ==========================================

    def between(
        self,
        start_date: date,
        end_date: date,
    ):

        return (
            self.db.query(Reading)
            .filter(
                Reading.reading_date >= start_date,
                Reading.reading_date <= end_date,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.asc())
            .all()
        )

    # ==========================================
    # FUTURE AUTOMATIC LECTIONARY
    # ==========================================

    def sync_official_lectionary(self):
        """
        Reserved for future integration with
        official Catholic lectionary providers.

        This method will automatically update:
        - Daily Readings
        - Saints
        - Liturgical Calendar
        - Liturgical Seasons
        - Liturgical Year (A/B/C)
        """
        return {
            "success": False,
            "message": "Official lectionary synchronization is not yet enabled.",
        }
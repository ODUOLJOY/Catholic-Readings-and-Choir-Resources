from datetime import date
from sqlalchemy.orm import Session

from app.models.readings import Reading
from app.services.calendar import get_calendar_info


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

    def get_today_readings(self):
        return self.get_readings(date.today())

    def get_readings(self, reading_date: date):

        reading = (
            self.db.query(Reading)
            .filter(
                Reading.reading_date == reading_date,
                Reading.is_published == True,
            )
            .first()
        )

        return {
            "date": reading_date,
            "calendar": get_calendar_info(reading_date),
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
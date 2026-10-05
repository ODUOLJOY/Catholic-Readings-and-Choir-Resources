from datetime import date
from sqlalchemy.orm import Session

from app.models.readings import Reading
from app.services.calendar import get_calendar_info, kenya_today
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
        return LiturgicalSyncService.sync_date(db, kenya_today())

    def get_today_readings(self, language: str = "English"):
        return self.get_readings(kenya_today(), language)

    def _select_reading_set(self, day):
        sets = sorted(day.reading_sets, key=lambda reading_set: reading_set.id or 0)
        if not sets:
            return None

        by_status = {}
        for reading_set in sets:
            by_status.setdefault(reading_set.selection_status.lower(), reading_set)

        rank = day.celebration_rank.strip().lower()
        proper = by_status.get("strictly_proper") or by_status.get("proper")
        weekday = by_status.get("weekday_default")

        if rank == "solemnity":
            return proper
        if rank == "feast":
            return proper or weekday
        if "memorial" in rank:
            if "strictly proper" in rank or "obligatory" in rank:
                return by_status.get("strictly_proper") or weekday
            return weekday or by_status.get("common_option") or by_status.get("suggested")
        return weekday or proper

    def get_readings(self, reading_date: date, language: str = "English"):
        from app.models.liturgical import LiturgicalDay, ReadingSet

        day = self.db.query(LiturgicalDay).filter(LiturgicalDay.date == reading_date).first()

        reading = (
            self.db.query(Reading)
            .filter(
                Reading.reading_date == reading_date,
                Reading.published == True,
                Reading.language.ilike(language),
            )
            .order_by(Reading.id)
            .first()
        )

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
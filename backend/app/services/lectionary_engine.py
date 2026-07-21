from datetime import date

from sqlalchemy.orm import Session

from app.models.readings import Reading
from app.services.calendar import (
    get_calendar_info,
    get_liturgical_year,
)


class LectionaryEngine:
    """
    Retrieves Catholic Mass readings from the database.

    The architecture is ready for future automatic
    synchronization with official Catholic lectionary
    providers without changing the API.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_today(self):
        return self.get_by_date(date.today())

    def get_by_date(self, reading_date: date):

        reading = (
            self.db.query(Reading)
            .filter(Reading.reading_date == reading_date)
            .first()
        )

        if reading:

            return {
                "source": "database",
                "reading": reading,
                "calendar": get_calendar_info(reading_date),
            }

        return {
            "source": "calendar",
            "reading": None,
            "calendar": get_calendar_info(reading_date),
            "message": "No reading uploaded for this date.",
        }

    def get_range(
        self,
        start_date: date,
        end_date: date,
    ):

        readings = (
            self.db.query(Reading)
            .filter(
                Reading.reading_date >= start_date,
                Reading.reading_date <= end_date,
            )
            .order_by(Reading.reading_date)
            .all()
        )

        return readings

    def search_feast(self, feast: str):

        return (
            self.db.query(Reading)
            .filter(
                Reading.feast.ilike(f"%{feast}%")
            )
            .all()
        )

    def search_reference(self, bible_reference: str):

        return (
            self.db.query(Reading)
            .filter(
                Reading.first_reading_reference.ilike(
                    f"%{bible_reference}%"
                )
            )
            .all()
        )

    def readings_for_year(
        self,
        year: int,
    ):

        return (
            self.db.query(Reading)
            .filter(
                Reading.liturgical_year == year
            )
            .all()
        )

    def current_liturgical_cycle(self):

        return get_liturgical_year(date.today())
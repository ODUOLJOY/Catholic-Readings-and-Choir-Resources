from datetime import date

from sqlalchemy.orm import Session

from app.models.readings import Reading


class ReadingService:

    @staticmethod
    def get_today(db: Session):
        return (
            db.query(Reading)
            .filter(
                Reading.reading_date == date.today(),
                Reading.is_published == True,
            )
            .first()
        )

    @staticmethod
    def get_by_date(
        db: Session,
        reading_date: date,
    ):
        return (
            db.query(Reading)
            .filter(
                Reading.reading_date == reading_date,
                Reading.is_published == True,
            )
            .first()
        )

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 30,
    ):
        return (
            db.query(Reading)
            .filter(
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        reading: Reading,
    ):
        db.add(reading)
        db.commit()
        db.refresh(reading)
        return reading

    @staticmethod
    def update(
        db: Session,
        reading_id: int,
        data: dict,
    ):
        reading = (
            db.query(Reading)
            .filter(Reading.id == reading_id)
            .first()
        )

        if not reading:
            return None

        for key, value in data.items():
            if hasattr(reading, key):
                setattr(reading, key, value)

        db.commit()
        db.refresh(reading)

        return reading

    @staticmethod
    def delete(
        db: Session,
        reading_id: int,
    ):
        reading = (
            db.query(Reading)
            .filter(Reading.id == reading_id)
            .first()
        )

        if not reading:
            return False

        db.delete(reading)
        db.commit()

        return True

    @staticmethod
    def search(
        db: Session,
        query: str,
    ):
        return (
            db.query(Reading)
            .filter(
                (Reading.feast.ilike(f"%{query}%"))
                | (Reading.saint.ilike(f"%{query}%"))
                | (Reading.first_reading_reference.ilike(f"%{query}%"))
                | (Reading.psalm_reference.ilike(f"%{query}%"))
                | (Reading.second_reading_reference.ilike(f"%{query}%"))
                | (Reading.gospel_reference.ilike(f"%{query}%"))
            )
            .order_by(Reading.reading_date.desc())
            .all()
        )

    @staticmethod
    def by_language(
        db: Session,
        language: str,
    ):
        return (
            db.query(Reading)
            .filter(
                Reading.language == language,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.desc())
            .all()
        )

    @staticmethod
    def by_season(
        db: Session,
        season: str,
    ):
        return (
            db.query(Reading)
            .filter(
                Reading.liturgical_season == season,
                Reading.is_published == True,
            )
            .order_by(Reading.reading_date.asc())
            .all()
        )

    @staticmethod
    def publish(
        db: Session,
        reading_id: int,
    ):
        reading = (
            db.query(Reading)
            .filter(Reading.id == reading_id)
            .first()
        )

        if not reading:
            return None

        reading.is_published = True

        db.commit()
        db.refresh(reading)

        return reading

    @staticmethod
    def unpublish(
        db: Session,
        reading_id: int,
    ):
        reading = (
            db.query(Reading)
            .filter(Reading.id == reading_id)
            .first()
        )

        if not reading:
            return None

        reading.is_published = False

        db.commit()
        db.refresh(reading)

        return reading
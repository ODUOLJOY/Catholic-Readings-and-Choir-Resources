from datetime import date
from sqlalchemy.orm import Session

from app.models.readings import Reading
from app.services.calendar import get_calendar_info


def get_today_readings(db: Session):
    return get_readings_by_date(db, date.today())


def get_readings_by_date(db: Session, reading_date: date):
    reading = (
        db.query(Reading)
        .filter(Reading.reading_date == reading_date)
        .first()
    )

    calendar = get_calendar_info(reading_date)

    return {
        "date": reading_date,
        "calendar": calendar,
        "reading": reading,
    }


def get_readings_between(
    db: Session,
    start_date: date,
    end_date: date,
):
    return (
        db.query(Reading)
        .filter(
            Reading.reading_date >= start_date,
            Reading.reading_date <= end_date,
        )
        .order_by(Reading.reading_date.asc())
        .all()
    )


def search_readings(
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
        .all()
    )


def get_by_season(
    db: Session,
    season: str,
):
    return (
        db.query(Reading)
        .filter(
            Reading.liturgical_season.ilike(season)
        )
        .order_by(Reading.reading_date.asc())
        .all()
    )


def get_by_feast(
    db: Session,
    feast: str,
):
    return (
        db.query(Reading)
        .filter(
            Reading.feast.ilike(f"%{feast}%")
        )
        .all()
    )


def get_by_saint(
    db: Session,
    saint: str,
):
    return (
        db.query(Reading)
        .filter(
            Reading.saint.ilike(f"%{saint}%")
        )
        .all()
    )


def get_by_language(
    db: Session,
    language: str,
):
    return (
        db.query(Reading)
        .filter(
            Reading.language == language
        )
        .order_by(Reading.reading_date.asc())
        .all()
    )


def get_latest(
    db: Session,
    limit: int = 10,
):
    return (
        db.query(Reading)
        .order_by(Reading.reading_date.desc())
        .limit(limit)
        .all()
    )
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.readings import Reading
from app.models.user import User
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)

router = APIRouter(
    prefix="/api/readings",
    tags=["Readings"],
)


# ==========================
# PUBLIC ROUTES
# ==========================

@router.get("/today")
def today_readings(db: Session = Depends(get_db)):
    today = date.today()

    reading = (
        db.query(Reading)
        .filter(
            Reading.reading_date == today,
            Reading.is_published == True,
        )
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Today's readings not available."
        )

    return reading


@router.get("/{reading_date}")
def get_reading_by_date(
    reading_date: date,
    db: Session = Depends(get_db),
):
    reading = (
        db.query(Reading)
        .filter(
            Reading.reading_date == reading_date,
            Reading.is_published == True,
        )
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    return reading


@router.get("/")
def all_readings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    language: str | None = None,
    season: str | None = None,
    year: str | None = None,
    feast: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Reading).filter(
        Reading.is_published == True
    )

    if language:
        query = query.filter(
            Reading.language == language
        )

    if season:
        query = query.filter(
            Reading.liturgical_season == season
        )

    if year:
        query = query.filter(
            Reading.liturgical_year == year
        )

    if feast:
        query = query.filter(
            Reading.feast.ilike(f"%{feast}%")
        )

    total = query.count()

    readings = (
        query.order_by(Reading.reading_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": readings,
    }


@router.get("/search/")
def search_readings(
    q: str,
    db: Session = Depends(get_db),
):
    results = (
        db.query(Reading)
        .filter(
            Reading.is_published == True,
            or_(
                Reading.first_reading.ilike(f"%{q}%"),
                Reading.psalm.ilike(f"%{q}%"),
                Reading.second_reading.ilike(f"%{q}%"),
                Reading.gospel.ilike(f"%{q}%"),
                Reading.feast.ilike(f"%{q}%"),
                Reading.saint.ilike(f"%{q}%"),
                Reading.reflection.ilike(f"%{q}%"),
            ),
        )
        .order_by(Reading.reading_date.desc())
        .all()
    )

    return results


# ==========================
# ADMIN ROUTES
# ==========================

@router.post("/")
def create_reading(
    reading: Reading,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exists = (
        db.query(Reading)
        .filter(
            Reading.reading_date == reading.reading_date,
            Reading.language == reading.language,
        )
        .first()
    )

    if exists:
        raise HTTPException(
            status_code=400,
            detail="Reading already exists."
        )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    return reading


@router.put("/{reading_id}")
def update_reading(
    reading_id: int,
    updated: Reading,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    for key, value in updated.__dict__.items():
        if key != "_sa_instance_state":
            setattr(reading, key, value)

    db.commit()
    db.refresh(reading)

    return reading


@router.delete("/{reading_id}")
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    db.delete(reading)
    db.commit()

    return {
        "message": "Reading deleted successfully."
    }


@router.post("/{reading_id}/publish")
def publish_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    reading.is_published = True

    db.commit()

    return {
        "message": "Reading published successfully."
    }


@router.post("/{reading_id}/unpublish")
def unpublish_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    reading.is_published = False

    db.commit()

    return {
        "message": "Reading unpublished successfully."
    }


@router.get("/me/bookmarks")
def my_bookmarks(
    current_user: User = Depends(get_current_user),
):
    return current_user.bookmarked_readings
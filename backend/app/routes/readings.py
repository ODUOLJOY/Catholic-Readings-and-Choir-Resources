from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.favorite import Favorite
from app.models.readings import Reading
from app.models.user import User
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)
from app.schemas.readings import ReadingCreate, ReadingResponse, ReadingUpdate
from app.services.calendar import kenya_today

router = APIRouter(
    prefix="/api/readings",
    tags=["Readings"],
)


# ==========================
# PUBLIC ROUTES
# ==========================

@router.get("/today")
def today_readings(
    language: str = Query("English"),
    db: Session = Depends(get_db),
):
    today = kenya_today()

    reading = (
        db.query(Reading)
        .filter(
            Reading.reading_date == today,
            Reading.published == True,
            Reading.language.ilike(language),
        )
        .order_by(Reading.id)
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Today's readings not available."
        )

    return reading


@router.get("/id/{reading_id}")
def get_reading_by_id(
    reading_id: int,
    db: Session = Depends(get_db),
):
    reading = (
        db.query(Reading)
        .filter(
            Reading.id == reading_id,
            Reading.published == True,
        )
        .first()
    )

    if not reading:
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    return reading


@router.get("/{reading_date}")
def get_reading_by_date(
    reading_date: date,
    language: str = Query("English"),
    db: Session = Depends(get_db),
):
    reading = (
        db.query(Reading)
        .filter(
            Reading.reading_date == reading_date,
            Reading.published == True,
            Reading.language.ilike(language),
        )
        .order_by(Reading.id)
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
        Reading.published == True
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
    language: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Full-text search across reading content.

    Previously this ran ``.all()`` with no limit, so a single request against a
    table of full liturgical texts had to materialise every matching row and
    every one of them carries seven large text columns. One request could exhaust
    the server's memory. The result set is now bounded and paginated, matching the
    list endpoint.
    """
    query = db.query(Reading).filter(Reading.published == True)
    if language:
        query = query.filter(Reading.language.ilike(language))
    results = (
        query.filter(
            or_(
                Reading.first_reading.ilike(f"%{q}%"),
                Reading.responsorial_psalm.ilike(f"%{q}%"),
                Reading.second_reading.ilike(f"%{q}%"),
                Reading.gospel.ilike(f"%{q}%"),
                Reading.feast.ilike(f"%{q}%"),
                Reading.saint_of_day.ilike(f"%{q}%"),
                Reading.reflection.ilike(f"%{q}%"),
            ),
        )
        .order_by(Reading.reading_date.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return results


# ==========================
# ADMIN ROUTES
# ==========================

@router.post("/", response_model=ReadingResponse)
def create_reading(
    payload: ReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exists = (
        db.query(Reading)
        .filter(
            Reading.reading_date == payload.reading_date,
            Reading.language == payload.language,
        )
        .first()
    )

    if exists:
        raise HTTPException(
            status_code=400,
            detail="Reading already exists."
        )

    # ``published``, ``approved`` and ``uploaded_by`` are not taken from the
    # request body: a new reading starts unpublished and unapproved, and the
    # author comes from the authenticated session. The previous
    # ``Reading(**payload)`` let a request set all three directly, which bypassed
    # the moderation workflow.
    reading = Reading(
        **payload.model_dump(),
        published=False,
        approved=False,
        uploaded_by=current_user.id,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    return reading


@router.put("/{reading_id}", response_model=ReadingResponse)
def update_reading(
    reading_id: int,
    payload: ReadingUpdate,
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

    # Explicit field list instead of ``for key, value in payload.items()`` with a
    # ``hasattr`` check, which applied every model attribute the caller guessed.
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No editable fields supplied.")

    for field, value in changes.items():
        setattr(reading, field, value)

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

    reading.published = True

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

    reading.published = False

    db.commit()

    return {
        "message": "Reading unpublished successfully."
    }


@router.get("/me/bookmarks")
def my_bookmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Reading)
        .join(
            Favorite,
            Favorite.target_resource_id == Reading.id,
        )
        .filter(
            Favorite.user_id == current_user.id,
            Favorite.resource_type == "reading",
        )
        .order_by(Favorite.created_at.desc())
        .all()
    )
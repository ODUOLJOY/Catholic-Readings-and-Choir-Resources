from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.saint import Saint
from app.models.user import User
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)

router = APIRouter(
    prefix="/api/saints",
    tags=["Saints"],
)


# =====================================
# PUBLIC ROUTES
# =====================================

@router.get("/today")
def saint_of_today(db: Session = Depends(get_db)):
    today = date.today()

    saint = (
        db.query(Saint)
        .filter(Saint.feast_date == today)
        .first()
    )

    if not saint:
        raise HTTPException(
            status_code=404,
            detail="Saint of the day not found."
        )

    return saint


@router.get("/{saint_id}")
def get_saint(
    saint_id: int,
    db: Session = Depends(get_db),
):
    saint = (
        db.query(Saint)
        .filter(Saint.id == saint_id)
        .first()
    )

    if not saint:
        raise HTTPException(
            status_code=404,
            detail="Saint not found."
        )

    return saint


@router.get("/")
def all_saints(
    db: Session = Depends(get_db),
):
    saints = (
        db.query(Saint)
        .order_by(Saint.name.asc())
        .all()
    )

    return saints


@router.get("/month/{month}")
def saints_by_month(
    month: int,
    db: Session = Depends(get_db),
):
    saints = (
        db.query(Saint)
        .filter(Saint.month == month)
        .order_by(Saint.day.asc())
        .all()
    )

    return saints


@router.get("/search/{keyword}")
def search_saints(
    keyword: str,
    db: Session = Depends(get_db),
):
    saints = (
        db.query(Saint)
        .filter(
            Saint.name.ilike(f"%{keyword}%")
        )
        .all()
    )

    return saints


# =====================================
# ADMIN ROUTES
# =====================================

@router.post("/")
def create_saint(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exists = (
        db.query(Saint)
        .filter(
            Saint.name == payload.get("name"),
            Saint.feast_date == payload.get("feast_date"),
        )
        .first()
    )

    if exists:
        raise HTTPException(
            status_code=400,
            detail="Saint already exists."
        )

    saint = Saint(**payload)
    if saint.month is None:
        saint.month = saint.feast_date.month
    if saint.day is None:
        saint.day = saint.feast_date.day
    db.add(saint)
    db.commit()
    db.refresh(saint)

    return saint


@router.put("/{saint_id}")
def update_saint(
    saint_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    saint = (
        db.query(Saint)
        .filter(Saint.id == saint_id)
        .first()
    )

    if not saint:
        raise HTTPException(
            status_code=404,
            detail="Saint not found."
        )

    for key, value in payload.items():
        if hasattr(Saint, key) and key != "id":
            setattr(saint, key, value)

    db.commit()
    db.refresh(saint)

    return saint


@router.delete("/{saint_id}")
def delete_saint(
    saint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    saint = (
        db.query(Saint)
        .filter(Saint.id == saint_id)
        .first()
    )

    if not saint:
        raise HTTPException(
            status_code=404,
            detail="Saint not found."
        )

    db.delete(saint)
    db.commit()

    return {
        "message": "Saint deleted successfully."
    }
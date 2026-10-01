from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.missal_engine import MissalEngine
from app.routes.admin import require_admin
from app.routes.auth_dependency import get_current_user
from app.models.user import User
from app.services.liturgical_sync import LiturgicalSyncService
from app.services.calendar import get_calendar_info

router = APIRouter(prefix="/api/v1/liturgy", tags=["Liturgy"])

@router.get("/today")
def get_today_liturgy(
    language: str = Query("English"),
    db: Session = Depends(get_db),
):
    engine = MissalEngine(db)
    return engine.get_today_readings(language)

@router.get("/date/{target_date}")
def get_liturgy_by_date(
    target_date: date,
    language: str = Query("English"),
    db: Session = Depends(get_db),
):
    engine = MissalEngine(db)
    return engine.get_readings(target_date, language)

@router.post("/admin/import")
def import_readings(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    
    # Validate structure (basic)
    if "date" not in data or "celebration" not in data:
        raise HTTPException(status_code=400, detail="Missing required fields: date, celebration")
        
    return LiturgicalSyncService.import_verified_data(db, data)

@router.get("/calendar")
def get_calendar(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
):
    from app.models.liturgical import LiturgicalDay
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must not precede start_date")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Calendar range cannot exceed 366 days")

    verified_days = db.query(LiturgicalDay).filter(
        LiturgicalDay.date >= start_date,
        LiturgicalDay.date <= end_date
    ).all()
    verified_by_date = {day.date: day for day in verified_days}

    calendar = []
    target_date = start_date
    while target_date <= end_date:
        info = get_calendar_info(target_date)
        verified_day = verified_by_date.get(target_date)
        if verified_day:
            info.update({
                "celebration": verified_day.celebration_name,
                "rank": verified_day.celebration_rank,
                "color": verified_day.liturgical_color,
                "season": verified_day.season,
                "verification_status": verified_day.verification_status,
            })
        calendar.append(info)
        target_date += timedelta(days=1)
    return calendar

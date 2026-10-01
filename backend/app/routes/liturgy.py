from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from app.db.database import get_db
from app.services.missal_engine import MissalEngine
from app.routes.admin import require_admin
from app.routes.auth_dependency import get_current_user
from app.models.user import User
from app.services.liturgical_sync import LiturgicalSyncService

router = APIRouter(prefix="/api/v1/liturgy", tags=["Liturgy"])

@router.get("/today")
def get_today_liturgy(db: Session = Depends(get_db)):
    engine = MissalEngine(db)
    # Ensure sync happens
    engine.sync_today(db)
    return engine.get_today_readings()

@router.get("/date/{target_date}")
def get_liturgy_by_date(target_date: date, db: Session = Depends(get_db)):
    engine = MissalEngine(db)
    return engine.get_readings(target_date)

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
    # Return list of calendar days in range
    days = db.query(LiturgicalDay).filter(
        LiturgicalDay.date >= start_date,
        LiturgicalDay.date <= end_date
    ).all()
    
    return days

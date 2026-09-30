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

@router.post("/admin/calendar/sync")
def import_calendar_data(
    data: dict, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    return LiturgicalSyncService.import_verified_data(db, data)

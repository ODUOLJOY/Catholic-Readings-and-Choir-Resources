from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.parish import ParishRequest
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.routes.admin import require_admin
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/parish-requests", tags=["Parish Requests"])

class ParishRequestCreate(BaseModel):
    parish_name: str
    jurisdiction_name: str = None
    deanery_name: str = None
    town: str = None
    details: str = None

@router.post("/")
def create_request(
    payload: ParishRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_request = ParishRequest(
        parish_name=payload.parish_name,
        jurisdiction_name=payload.jurisdiction_name,
        deanery_name=payload.deanery_name,
        town=payload.town,
        details=payload.details,
        submitted_by_id=current_user.id
    )
    db.add(new_request)
    db.commit()
    return new_request

@router.get("/")
def get_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    return db.query(ParishRequest).all()

@router.put("/{request_id}/status")
def update_status(
    request_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    req = db.query(ParishRequest).filter(ParishRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = status
    db.commit()
    return req

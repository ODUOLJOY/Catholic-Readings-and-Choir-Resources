from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.parish import Parish
from app.models.locations import Deanery
from app.routes.auth_dependency import get_current_user
from pydantic import BaseModel

class LocationUpdateRequest(BaseModel):
    parish_id: int
    deanery_id: int
    diocese_id: int

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.put("/me/location")
def update_user_location(
    payload: LocationUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    parish = db.query(Parish).filter(Parish.id == payload.parish_id).first()
    if not parish:
        raise HTTPException(status_code=404, detail="Parish not found")
        
    if parish.deanery_id != payload.deanery_id:
        raise HTTPException(status_code=400, detail="Parish does not belong to the selected deanery")
        
    if parish.diocese_id != payload.diocese_id:
        raise HTTPException(status_code=400, detail="Parish does not belong to the selected diocese")
        
    deanery = db.query(Deanery).filter(Deanery.id == payload.deanery_id).first()
    if not deanery:
        raise HTTPException(status_code=404, detail="Deanery not found")
    if deanery.diocese_id != payload.diocese_id:
        raise HTTPException(status_code=400, detail="Deanery does not belong to the selected diocese")

    user.parish_id = payload.parish_id
    user.profile_setup_completed = True
    db.commit()
    db.refresh(user)
    return user

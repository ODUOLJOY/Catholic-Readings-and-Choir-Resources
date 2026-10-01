from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.parish import Parish
from app.models.locations import Deanery
from app.models.community import CommunityAuditLog, ParishMembership
from app.routes.auth_dependency import get_current_user
from app.schemas.user import UserResponse

class LocationUpdateRequest(BaseModel):
    parish_id: int
    deanery_id: int
    diocese_id: int


class LocationUpdateResponse(UserResponse):
    parish_membership_status: str | None = None
    model_config = ConfigDict(from_attributes=True)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.put("/me/location", response_model=LocationUpdateResponse)
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

    if user.parish_id != payload.parish_id:
        db.query(ParishMembership).filter(
            ParishMembership.user_id == user.id,
            ParishMembership.status == "active",
        ).update(
            {
                ParishMembership.status: "transferred",
                ParishMembership.review_note: "Member changed parish affiliation.",
                ParishMembership.reviewed_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        membership = db.query(ParishMembership).filter(
            ParishMembership.user_id == user.id,
            ParishMembership.parish_id == payload.parish_id,
        ).first()
        if membership is None:
            membership = ParishMembership(
                user_id=user.id,
                parish_id=payload.parish_id,
                status="pending",
            )
            db.add(membership)
        else:
            membership.status = "pending"
            membership.reviewed_by = None
            membership.reviewed_at = None
            membership.review_note = None
        db.flush()
        db.add(
            CommunityAuditLog(
                actor_id=user.id,
                action="parish_membership.requested",
                target_type="parish_membership",
                target_id=membership.id,
                scope_type="parish",
                scope_id=payload.parish_id,
            )
        )
    user.parish_id = payload.parish_id
    user.profile_setup_completed = True
    db.commit()
    db.refresh(user)
    membership = db.query(ParishMembership).filter(
        ParishMembership.user_id == user.id,
        ParishMembership.parish_id == payload.parish_id,
    ).first()
    return LocationUpdateResponse.model_validate(user).model_copy(
        update={"parish_membership_status": membership.status if membership else None}
    )

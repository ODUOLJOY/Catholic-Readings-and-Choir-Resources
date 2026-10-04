from datetime import datetime, timezone
from typing import Optional

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
from app.services import hierarchy_service

class LocationUpdateRequest(BaseModel):
    """Parish selection for the signed-in user.

    ``parish_id`` is the only field required. The deanery, diocese and
    ecclesiastical province are derived from the parish on the server. The
    optional ``deanery_id`` / ``diocese_id`` fields are still accepted for
    backwards compatibility with older clients, but when present they are
    validated rather than trusted.
    """

    parish_id: int
    deanery_id: Optional[int] = None
    diocese_id: Optional[int] = None


class LocationUpdateResponse(UserResponse):
    parish_membership_status: str | None = None
    model_config = ConfigDict(from_attributes=True)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("/me/location")
def get_user_location(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    parish = db.query(Parish).filter(Parish.id == user.parish_id).first()
    if parish is None:
        return {"diocese_id": None, "deanery_id": None, "parish_id": None}

    deanery = db.query(Deanery).filter(
        Deanery.id == parish.deanery_id,
        Deanery.diocese_id == parish.diocese_id,
    ).first()
    if deanery is None:
        return {"diocese_id": None, "deanery_id": None, "parish_id": None}

    return {
        "diocese_id": deanery.diocese_id,
        "deanery_id": deanery.id,
        "parish_id": parish.id,
    }


@router.put("/me/location", response_model=LocationUpdateResponse)
def update_user_location(
    payload: LocationUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Resolve and validate the full ancestry from the parish alone. The client
    # cannot introduce an inconsistent province / diocese / deanery combination.
    try:
        resolved = hierarchy_service.resolve_parish_by_id(
            db, payload.parish_id, require_active=True
        )
    except hierarchy_service.HierarchyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.deanery_id is not None and payload.deanery_id != resolved.deanery.id:
        raise HTTPException(
            status_code=400,
            detail="Parish does not belong to the selected deanery",
        )

    if payload.diocese_id is not None and payload.diocese_id != resolved.diocese.id:
        raise HTTPException(
            status_code=400,
            detail="Parish does not belong to the selected diocese",
        )

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

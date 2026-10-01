from datetime import datetime, timezone
import hmac
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.config import settings
from app.models.community import (
    CommunityAnnouncement,
    CommunityAuditLog,
    CommunityConversation,
    CommunityEvent,
    CommunityGroup,
    CommunityMessage,
    CommunityNotificationPreference,
    CommunitySuggestion,
    ConversationMember,
    GroupMembership,
    MemberBlock,
    MessageReaction,
    ParishMembership,
    PrayerIntention,
    PrayerReaction,
    RoleAssignment,
    RoleRequest,
)
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.notification import Notification
from app.models.report import ContentReport
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services.authorization import (
    can_manage_community_scope,
    can_review_role_request,
    scope_exists,
    user_belongs_to_scope,
)

router = APIRouter(prefix="/api/community", tags=["Community"])

ROLE_SCOPES: dict[str, set[str]] = {
    "diocesan_admin": {"diocese"},
    "parish_admin": {"parish"},
    "parish_music_director": {"parish", "group"},
    "choir_director": {"parish", "group"},
    "catechist": {"parish", "group"},
    "youth_coordinator": {"parish", "group"},
    "moderator": {"diocese", "parish", "group"},
    "ministry_leader": {"group"},
}
SUGGESTION_CATEGORIES = {
    "liturgy", "youth", "choir_music", "catechesis", "parish_activities",
    "charity", "evangelization", "technology", "community", "other",
}


class RoleRequestCreate(BaseModel):
    requested_role: str
    scope_type: str
    scope_id: int = Field(gt=0)
    ministry: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=10, max_length=4000)
    supporting_information: str | None = Field(default=None, max_length=4000)


class RoleRequestReview(BaseModel):
    status: Literal["under_review", "more_information_required", "approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=4000)


class ParishMembershipReview(BaseModel):
    status: Literal["active", "rejected"]
    review_note: str | None = Field(default=None, max_length=4000)


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    announcement_type: str = Field(default="general", max_length=30)
    audience_type: Literal["platform", "diocese", "parish", "group"]
    audience_id: int | None = Field(default=None, gt=0)
    status: Literal["draft", "scheduled"] = "draft"
    scheduled_at: datetime | None = None
    attachment_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_audience(self):
        if self.audience_type == "platform" and self.audience_id is not None:
            raise ValueError("Platform announcements cannot have a target ID.")
        if self.audience_type != "platform" and self.audience_id is None:
            raise ValueError("A target ID is required for scoped announcements.")
        if self.status == "scheduled" and self.scheduled_at is None:
            raise ValueError("Scheduled announcements require a publication time.")
        return self


class SuggestionCreate(BaseModel):
    category: str
    body: str = Field(min_length=10, max_length=10000)
    scope_type: Literal["diocese", "parish"]
    scope_id: int = Field(gt=0)
    is_anonymous: bool = False


class ReviewStatus(BaseModel):
    status: str
    review_note: str | None = Field(default=None, max_length=4000)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    scope_type: Literal["diocese", "parish", "group"]
    scope_id: int = Field(gt=0)
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)


class PrayerCreate(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)
    visibility: Literal["private", "parish", "diocese", "public"] = "private"


class NotificationPreferencesUpdate(BaseModel):
    announcements: bool
    events: bool
    role_requests: bool
    messages: bool


class PrayerReactionCreate(BaseModel):
    reaction: Literal["praying"] = "praying"


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    scope_type: Literal["diocese", "parish"]
    scope_id: int = Field(gt=0)


class ConversationCreate(BaseModel):
    scope_type: Literal["parish", "group"]
    scope_id: int = Field(gt=0)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    reply_to_id: int | None = Field(default=None, gt=0)


class ReactionCreate(BaseModel):
    reaction: str = Field(min_length=1, max_length=20)


class BlockCreate(BaseModel):
    user_id: int = Field(gt=0)


def _audit(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: int | None,
    scope_type: str | None = None,
    scope_id: int | None = None,
    reason: str | None = None,
    role: str | None = None,
) -> None:
    db.add(
        CommunityAuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
        )
    )


def _require_member_scope(
    db: Session,
    user: User,
    scope_type: str,
    scope_id: int,
) -> None:
    if not user_belongs_to_scope(db, user, scope_type, scope_id):
        raise HTTPException(status_code=403, detail="You are not a member of this community scope.")


def _require_manage_scope(
    db: Session,
    user: User,
    scope_type: str,
    scope_id: int,
) -> None:
    if not can_manage_community_scope(db, user, scope_type, scope_id):
        raise HTTPException(status_code=403, detail="You cannot administer this community scope.")


def _visible_announcement(db: Session, user: User, item: CommunityAnnouncement) -> bool:
    if item.audience_type == "platform":
        return True
    if item.audience_id is None:
        return False
    return user_belongs_to_scope(db, user, item.audience_type, item.audience_id)


def _notify_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    category: str,
) -> None:
    preference = db.query(CommunityNotificationPreference).filter(
        CommunityNotificationPreference.user_id == user_id
    ).first()
    if preference is not None and not getattr(preference, category):
        return
    db.add(Notification(user_id=user_id, title=title, body=body))


def _scope_recipients(db: Session, scope_type: str, scope_id: int | None) -> list[int]:
    if scope_type == "platform":
        return [
            row[0] for row in db.query(User.id).filter(User.is_active.is_(True)).all()
        ]
    if scope_id is None:
        return []
    if scope_type == "parish":
        return [
            row[0]
            for row in db.query(ParishMembership.user_id)
            .join(User, User.id == ParishMembership.user_id)
            .filter(
                ParishMembership.parish_id == scope_id,
                ParishMembership.status == "active",
                User.is_active.is_(True),
            )
            .all()
        ]
    if scope_type == "diocese":
        return [
            row[0]
            for row in db.query(ParishMembership.user_id)
            .join(User, User.id == ParishMembership.user_id)
            .join(Parish, Parish.id == ParishMembership.parish_id)
            .filter(
                Parish.diocese_id == scope_id,
                ParishMembership.status == "active",
                User.is_active.is_(True),
            )
            .distinct()
            .all()
        ]
    if scope_type == "group":
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == scope_id,
            CommunityGroup.is_active.is_(True),
        ).first()
        if group is None:
            return []
        users = db.query(User).join(
            GroupMembership, GroupMembership.user_id == User.id
        ).filter(
            GroupMembership.group_id == scope_id,
            User.is_active.is_(True),
        ).all()
        return [
            member.id for member in users
            if user_belongs_to_scope(db, member, group.scope_type, group.scope_id)
        ]
    return []


@router.get("/me")
def community_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    roles = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user.id,
        RoleAssignment.is_active.is_(True),
    ).order_by(RoleAssignment.granted_at.desc()).all()
    requests = db.query(RoleRequest).filter(
        RoleRequest.requester_id == user.id,
        RoleRequest.status.in_(["submitted", "under_review", "more_information_required"]),
    ).count()
    parish = db.query(Parish).filter(Parish.id == user.parish_id).first() if user.parish_id else None
    deanery = db.query(Deanery).filter(Deanery.id == parish.deanery_id).first() if parish and parish.deanery_id else None
    diocese = db.query(Diocese).filter(Diocese.id == parish.diocese_id).first() if parish and parish.diocese_id else None
    membership = db.query(ParishMembership).filter(
        ParishMembership.user_id == user.id,
        ParishMembership.parish_id == user.parish_id,
    ).first() if user.parish_id else None
    return {
        "parish_id": user.parish_id,
        "parish_name": parish.name if parish else None,
        "diocese_id": parish.diocese_id if parish else None,
        "diocese_name": diocese.name if diocese else None,
        "deanery_id": parish.deanery_id if parish else None,
        "deanery_name": deanery.name if deanery else None,
        "roles": [
            {
                "id": role.id,
                "role": role.role,
                "scope_type": role.scope_type,
                "scope_id": role.scope_id,
                "ministry": role.ministry,
                "granted_at": role.granted_at,
            }
            for role in roles
        ],
        "pending_role_requests": requests,
        "parish_membership_status": membership.status if membership else None,
    }


@router.get("/memberships/mine")
def my_parish_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(ParishMembership, Parish).join(
        Parish, Parish.id == ParishMembership.parish_id
    ).filter(
        ParishMembership.user_id == user.id
    ).order_by(ParishMembership.requested_at.desc()).all()
    return [
        {
            "id": membership.id,
            "parish_id": parish.id,
            "parish_name": parish.name,
            "status": membership.status,
            "requested_at": membership.requested_at,
            "review_note": membership.review_note,
        }
        for membership, parish in rows
    ]


@router.post("/memberships/request")
def request_current_parish_membership(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.parish_id is None:
        raise HTTPException(status_code=400, detail="Select a parish in your profile first.")
    membership = db.query(ParishMembership).filter(
        ParishMembership.user_id == user.id,
        ParishMembership.parish_id == user.parish_id,
    ).first()
    if membership is None:
        membership = ParishMembership(
            user_id=user.id,
            parish_id=user.parish_id,
            status="pending",
        )
        db.add(membership)
        db.flush()
    elif membership.status == "active":
        return {"id": membership.id, "status": membership.status}
    elif membership.status == "pending":
        raise HTTPException(status_code=409, detail="Your parish membership request is already pending.")
    else:
        membership.status = "pending"
        membership.reviewed_by = None
        membership.reviewed_at = None
        membership.review_note = None
    _audit(
        db, user, "parish_membership.requested", "parish_membership",
        membership.id, "parish", user.parish_id,
    )
    db.commit()
    return {"id": membership.id, "status": membership.status}


@router.get("/memberships/review")
def reviewable_parish_memberships(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(ParishMembership, User).join(
        User, User.id == ParishMembership.user_id
    ).filter(
        ParishMembership.status == "pending"
    ).order_by(ParishMembership.requested_at.asc()).limit(500).all()
    return [
        {
            "id": membership.id,
            "user_id": membership.user_id,
            "full_name": member.full_name,
            "email": member.email,
            "parish_id": membership.parish_id,
            "parish_name": db.query(Parish.name).filter(
                Parish.id == membership.parish_id
            ).scalar(),
            "status": membership.status,
            "requested_at": membership.requested_at,
        }
        for membership, member in items
        if can_manage_community_scope(db, user, "parish", membership.parish_id)
    ]


@router.patch("/memberships/{membership_id}")
def review_parish_membership(
    membership_id: int,
    payload: ParishMembershipReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = db.query(ParishMembership).filter(
        ParishMembership.id == membership_id
    ).with_for_update().first()
    if membership is None or membership.status != "pending":
        raise HTTPException(status_code=404, detail="Pending parish membership not found.")
    if membership.user_id == user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own parish membership.")
    _require_manage_scope(db, user, "parish", membership.parish_id)
    if payload.status == "rejected" and not payload.review_note:
        raise HTTPException(status_code=422, detail="A rejection reason is required.")
    membership.status = payload.status
    membership.reviewed_by = user.id
    membership.reviewed_at = datetime.now(timezone.utc)
    membership.review_note = payload.review_note
    _audit(
        db, user, f"parish_membership.{payload.status}",
        "parish_membership", membership.id, "parish", membership.parish_id,
        payload.review_note,
    )
    db.add(
        Notification(
            user_id=membership.user_id,
            title="Parish membership reviewed",
            body=f"Your parish membership request was {payload.status}.",
        )
    )
    db.commit()
    return {
        "id": membership.id,
        "status": membership.status,
        "review_note": membership.review_note,
    }


@router.get("/role-requests/mine")
def my_role_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(RoleRequest)
        .filter(RoleRequest.requester_id == user.id)
        .order_by(RoleRequest.created_at.desc())
        .all()
    )


@router.post("/role-requests", status_code=201)
def create_role_request(
    payload: RoleRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    permitted_scopes = ROLE_SCOPES.get(payload.requested_role)
    if not permitted_scopes or payload.scope_type not in permitted_scopes:
        raise HTTPException(status_code=422, detail="Role cannot be requested for this scope.")
    if payload.requested_role == "diocesan_admin" and user.role == "super_admin":
        raise HTTPException(status_code=409, detail="Platform administrators must use the controlled appointment workflow.")
    if not scope_exists(db, payload.scope_type, payload.scope_id):
        raise HTTPException(status_code=404, detail="Requested scope was not found.")
    if not user_belongs_to_scope(db, user, payload.scope_type, payload.scope_id):
        raise HTTPException(status_code=403, detail="You must belong to the requested community scope.")
    existing = (
        db.query(RoleRequest.id)
        .filter(
            RoleRequest.requester_id == user.id,
            RoleRequest.requested_role == payload.requested_role,
            RoleRequest.scope_type == payload.scope_type,
            RoleRequest.scope_id == payload.scope_id,
            RoleRequest.status.in_(["submitted", "under_review", "more_information_required"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="A request for this role and scope is already pending.")
    request = RoleRequest(
        requester_id=user.id,
        requested_role=payload.requested_role,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        ministry=payload.ministry,
        reason=payload.reason,
        supporting_information=payload.supporting_information,
    )
    db.add(request)
    db.flush()
    reviewer_ids = {
        row[0] for row in db.query(User.id).filter(User.role == "super_admin").all()
    }
    reviewers = db.query(User).join(
        RoleAssignment, RoleAssignment.user_id == User.id
    ).filter(
            RoleAssignment.is_active.is_(True),
            RoleAssignment.role.in_(["parish_admin", "diocesan_admin"]),
        ).all()
    reviewer_ids.update(
        reviewer.id for reviewer in reviewers
        if can_review_role_request(
            db,
            reviewer,
            request.requested_role,
            request.scope_type,
            request.scope_id,
        )
    )
    for reviewer_id in reviewer_ids:
        _notify_user(
            db, reviewer_id, "Role request for review",
            "A member submitted a role request in your authorized scope.",
            "role_requests",
        )
    _audit(
        db, user, "role_request.submitted", "role_request", request.id,
        payload.scope_type, payload.scope_id, role=payload.requested_role,
    )
    db.commit()
    db.refresh(request)
    return request


@router.get("/role-requests/review")
def reviewable_role_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    requests = (
        db.query(RoleRequest)
        .filter(RoleRequest.status.in_(["submitted", "under_review", "more_information_required"]))
        .order_by(RoleRequest.created_at.asc())
        .limit(500)
        .all()
    )
    return [
        item for item in requests
        if can_review_role_request(
            db, user, item.requested_role, item.scope_type, item.scope_id
        )
    ]


@router.post("/prayer-intentions/{intention_id}/reactions", status_code=201)
def react_to_prayer_intention(
    intention_id: int,
    payload: PrayerReactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(PrayerIntention).filter(
        PrayerIntention.id == intention_id,
        PrayerIntention.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Prayer intention not found.")
    if item.user_id != user.id:
        visible = item.visibility == "public"
        visible = visible or (
            item.visibility == "parish"
            and item.parish_id is not None
            and user_belongs_to_scope(db, user, "parish", item.parish_id)
        )
        visible = visible or (
            item.visibility == "diocese"
            and item.diocese_id is not None
            and user_belongs_to_scope(db, user, "diocese", item.diocese_id)
        )
        if not visible:
            raise HTTPException(status_code=404, detail="Prayer intention not found.")
    existing = db.query(PrayerReaction).filter(
        PrayerReaction.intention_id == item.id,
        PrayerReaction.user_id == user.id,
    ).first()
    if existing:
        return {"intention_id": item.id, "status": "already_reacted"}
    db.add(
        PrayerReaction(
            intention_id=item.id,
            user_id=user.id,
            reaction=payload.reaction,
        )
    )
    db.commit()
    return {"intention_id": item.id, "status": "reacted"}


@router.get("/notification-preferences")
def get_notification_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    preference = db.query(CommunityNotificationPreference).filter(
        CommunityNotificationPreference.user_id == user.id
    ).first()
    if preference is None:
        return {
            "announcements": True,
            "events": True,
            "role_requests": True,
            "messages": True,
        }
    return {
        "announcements": preference.announcements,
        "events": preference.events,
        "role_requests": preference.role_requests,
        "messages": preference.messages,
    }


@router.put("/notification-preferences")
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    preference = db.query(CommunityNotificationPreference).filter(
        CommunityNotificationPreference.user_id == user.id
    ).first()
    if preference is None:
        preference = CommunityNotificationPreference(user_id=user.id)
        db.add(preference)
    for key, value in payload.model_dump().items():
        setattr(preference, key, value)
    db.commit()
    return payload.model_dump()


@router.patch("/role-requests/{request_id}")
def decide_role_request(
    request_id: int,
    payload: RoleRequestReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request = db.query(RoleRequest).filter(RoleRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Role request not found.")
    if request.requester_id == user.id:
        raise HTTPException(status_code=403, detail="You cannot review your own role request.")
    if not can_review_role_request(
        db, user, request.requested_role, request.scope_type, request.scope_id
    ):
        raise HTTPException(status_code=403, detail="You cannot review this role request.")
    if request.status in {"approved", "rejected"}:
        raise HTTPException(status_code=409, detail="This role request has already been decided.")
    if payload.status in {"more_information_required", "rejected"} and not payload.review_note:
        raise HTTPException(status_code=422, detail="A review note is required for this decision.")

    request.status = payload.status
    request.reviewer_id = user.id
    request.review_note = payload.review_note
    request.reviewed_at = datetime.now(timezone.utc)
    if payload.status == "approved":
        existing_assignment = db.query(RoleAssignment.id).filter(
            RoleAssignment.user_id == request.requester_id,
            RoleAssignment.role == request.requested_role,
            RoleAssignment.scope_type == request.scope_type,
            RoleAssignment.scope_id == request.scope_id,
            RoleAssignment.ministry == request.ministry,
            RoleAssignment.is_active.is_(True),
        ).first()
        if existing_assignment:
            raise HTTPException(status_code=409, detail="This user already has the requested role assignment.")
        assignment = RoleAssignment(
            user_id=request.requester_id,
            role=request.requested_role,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            ministry=request.ministry,
            granted_by=user.id,
        )
        db.add(assignment)
    _notify_user(
        db,
        request.requester_id,
        "Role request updated",
        f"Your {request.requested_role} request is now {payload.status}.",
        "role_requests",
    )
    _audit(
        db, user, f"role_request.{payload.status}", "role_request", request.id,
        request.scope_type, request.scope_id, payload.review_note, request.requested_role,
    )
    db.commit()
    db.refresh(request)
    return request


@router.get("/role-assignments")
def list_role_assignments(
    scope_type: str | None = None,
    scope_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "super_admin":
        if scope_type is None or scope_id is None:
            raise HTTPException(status_code=403, detail="A manageable scope is required.")
        _require_manage_scope(db, user, scope_type, scope_id)
    query = db.query(RoleAssignment).filter(RoleAssignment.is_active.is_(True))
    if scope_type is not None:
        query = query.filter(RoleAssignment.scope_type == scope_type)
    if scope_id is not None:
        query = query.filter(RoleAssignment.scope_id == scope_id)
    return query.order_by(RoleAssignment.granted_at.desc()).limit(500).all()


@router.get("/administrators")
def list_administrators(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(RoleAssignment, User).join(
        User, User.id == RoleAssignment.user_id
    ).filter(
        RoleAssignment.is_active.is_(True),
        RoleAssignment.role != "member",
    ).order_by(RoleAssignment.granted_at.desc()).limit(1000).all()
    return [
        {
            "assignment_id": assignment.id,
            "user_id": person.id,
            "full_name": person.full_name,
            "email": person.email,
            "role": assignment.role,
            "scope_type": assignment.scope_type,
            "scope_id": assignment.scope_id,
            "ministry": assignment.ministry,
            "granted_at": assignment.granted_at,
            "granted_by": assignment.granted_by,
            "is_active": person.is_active,
        }
        for assignment, person in rows
        if user.role == "super_admin"
        or can_manage_community_scope(
            db, user, assignment.scope_type, assignment.scope_id or 0
        )
    ]


@router.delete("/role-assignments/{assignment_id}")
def revoke_role_assignment(
    assignment_id: int,
    reason: str = Query(min_length=3, max_length=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assignment = db.query(RoleAssignment).filter(RoleAssignment.id == assignment_id).with_for_update().first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Role assignment not found.")
    if assignment.role == "super_admin" and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a super administrator can revoke a platform role.")
    if not can_review_role_request(
        db,
        user,
        assignment.role,
        assignment.scope_type,
        assignment.scope_id or 0,
    ):
        raise HTTPException(status_code=403, detail="You cannot revoke this role assignment.")
    _require_manage_scope(db, user, assignment.scope_type, assignment.scope_id or 0)
    assignment.is_active = False
    assignment.revoked_by = user.id
    assignment.revoked_at = datetime.now(timezone.utc)
    _audit(
        db, user, "role_assignment.revoked", "role_assignment", assignment.id,
        assignment.scope_type, assignment.scope_id, reason, assignment.role,
    )
    db.commit()
    return {"id": assignment.id, "status": "revoked"}


@router.get("/announcements")
def list_announcements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(CommunityAnnouncement)
        .filter(CommunityAnnouncement.status == "published")
        .order_by(CommunityAnnouncement.published_at.desc(), CommunityAnnouncement.scheduled_at.desc())
        .limit(500)
        .all()
    )
    return [item for item in items if _visible_announcement(db, user, item)]


@router.post("/system/publish-scheduled")
def publish_scheduled_announcements(
    x_job_token: str | None = Header(default=None, alias="X-Job-Token"),
    db: Session = Depends(get_db),
):
    expected = settings.SCHEDULED_JOB_TOKEN
    if not expected:
        raise HTTPException(status_code=503, detail="Scheduled publishing is not configured.")
    if not x_job_token or not hmac.compare_digest(x_job_token, expected):
        raise HTTPException(status_code=401, detail="Invalid job credential.")
    now = datetime.now(timezone.utc)
    items = db.query(CommunityAnnouncement).filter(
        CommunityAnnouncement.status == "scheduled",
        CommunityAnnouncement.scheduled_at <= now,
    ).with_for_update(skip_locked=True).limit(100).all()
    for item in items:
        item.status = "published"
        item.published_at = now
        db.add(
            CommunityAuditLog(
                actor_type="system",
                action="announcement.auto_published",
                target_type="announcement",
                target_id=item.id,
                role="scheduled_job",
                scope_type=item.audience_type,
                scope_id=item.audience_id,
                reason="Scheduled publication time reached.",
            )
        )
        for recipient_id in _scope_recipients(
            db, item.audience_type, item.audience_id
        ):
            _notify_user(db, recipient_id, item.title, item.body[:500], "announcements")
    db.commit()
    return {"published": len(items)}


@router.post("/announcements", status_code=201)
def create_announcement(
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.audience_type == "platform":
        if user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a super administrator can publish platform announcements.")
    else:
        if not scope_exists(db, payload.audience_type, payload.audience_id or 0):
            raise HTTPException(status_code=404, detail="Announcement audience not found.")
        _require_manage_scope(db, user, payload.audience_type, payload.audience_id or 0)
    if payload.status == "scheduled" and payload.scheduled_at:
        scheduled_time = payload.scheduled_at
        if scheduled_time.tzinfo is None:
            raise HTTPException(status_code=422, detail="Scheduled publication time must include a timezone.")
        if scheduled_time <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Scheduled publication time must be in the future.")
    announcement = CommunityAnnouncement(
        author_id=user.id,
        **payload.model_dump(),
        published_at=datetime.now(timezone.utc) if payload.status == "published" else None,
    )
    db.add(announcement)
    db.flush()
    _audit(
        db, user, f"announcement.{payload.status}", "announcement", announcement.id,
        payload.audience_type, payload.audience_id,
    )
    db.commit()
    db.refresh(announcement)
    return announcement


@router.get("/announcements/manage")
def manage_announcements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(CommunityAnnouncement).order_by(
        CommunityAnnouncement.created_at.desc()
    ).limit(500).all()
    if user.role == "super_admin":
        return items
    return [
        item for item in items
        if item.author_id == user.id
        or (
            item.audience_type != "platform"
            and item.audience_id is not None
            and can_manage_community_scope(
                db, user, item.audience_type, item.audience_id
            )
        )
    ]


@router.post("/announcements/{announcement_id}/publish")
def publish_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(CommunityAnnouncement).filter(
        CommunityAnnouncement.id == announcement_id
    ).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    if item.audience_type == "platform":
        if user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a super administrator can publish platform announcements.")
    else:
        _require_manage_scope(db, user, item.audience_type, item.audience_id or 0)
    if item.status not in {"draft", "scheduled"}:
        raise HTTPException(status_code=409, detail="Announcement is not publishable.")
    item.status = "published"
    item.published_at = datetime.now(timezone.utc)
    for recipient_id in _scope_recipients(db, item.audience_type, item.audience_id):
        _notify_user(db, recipient_id, item.title, item.body[:500], "announcements")
    _audit(
        db, user, "announcement.published", "announcement", item.id,
        item.audience_type, item.audience_id,
    )
    db.commit()
    return item


@router.post("/suggestions", status_code=201)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.category not in SUGGESTION_CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown suggestion category.")
    _require_member_scope(db, user, payload.scope_type, payload.scope_id)
    item = CommunitySuggestion(
        submitter_id=user.id,
        is_anonymous=payload.is_anonymous,
        category=payload.category,
        body=payload.body,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
    )
    db.add(item)
    db.flush()
    _audit(
        db, user, "suggestion.submitted", "suggestion", item.id,
        payload.scope_type, payload.scope_id,
    )
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "category": item.category,
        "body": item.body,
        "scope_type": item.scope_type,
        "scope_id": item.scope_id,
        "status": item.status,
        "is_anonymous": item.is_anonymous,
        "created_at": item.created_at,
    }


@router.get("/suggestions/mine")
def my_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(CommunitySuggestion).filter(
        CommunitySuggestion.submitter_id == user.id
    ).order_by(CommunitySuggestion.created_at.desc()).all()


@router.get("/suggestions/review")
def reviewable_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(CommunitySuggestion)
        .filter(CommunitySuggestion.status.notin_(["archived", "implemented", "declined"]))
        .order_by(CommunitySuggestion.created_at.asc())
        .limit(500)
        .all()
    )
    visible = [
        item for item in items
        if can_manage_community_scope(db, user, item.scope_type, item.scope_id)
    ]
    return [
        {
            "id": item.id,
            "category": item.category,
            "body": item.body,
            "scope_type": item.scope_type,
            "scope_id": item.scope_id,
            "status": item.status,
            "is_anonymous": item.is_anonymous,
            "submitter_id": None if item.is_anonymous else item.submitter_id,
            "created_at": item.created_at,
        }
        for item in visible
    ]


@router.patch("/suggestions/{suggestion_id}")
def update_suggestion(
    suggestion_id: int,
    payload: ReviewStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    allowed = {"under_review", "in_discussion", "accepted", "implemented", "declined", "archived"}
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail="Invalid suggestion status.")
    item = db.query(CommunitySuggestion).filter(
        CommunitySuggestion.id == suggestion_id
    ).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    _require_manage_scope(db, user, item.scope_type, item.scope_id)
    item.status = payload.status
    item.reviewer_id = user.id
    item.review_note = payload.review_note
    _audit(
        db, user, f"suggestion.{payload.status}", "suggestion", item.id,
        item.scope_type, item.scope_id, payload.review_note,
    )
    if item.submitter_id is not None:
        db.add(
            Notification(
                user_id=item.submitter_id,
                title="Suggestion reviewed",
                body=f"Your suggestion status is now {payload.status}.",
            )
        )
    db.commit()
    return {
        "id": item.id,
        "status": item.status,
        "review_note": item.review_note,
        "scope_type": item.scope_type,
        "scope_id": item.scope_id,
    }


@router.get("/events")
def list_events(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(CommunityEvent)
        .filter(CommunityEvent.is_published.is_(True))
        .order_by(CommunityEvent.starts_at.asc())
        .limit(500)
        .all()
    )
    return [
        item for item in items
        if user_belongs_to_scope(db, user, item.scope_type, item.scope_id)
    ]


@router.post("/events/{event_id}/publish")
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(CommunityEvent).filter(
        CommunityEvent.id == event_id
    ).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    _require_manage_scope(db, user, item.scope_type, item.scope_id)
    if item.is_published:
        raise HTTPException(status_code=409, detail="Event is already published.")
    item.is_published = True
    _audit(db, user, "event.published", "event", item.id, item.scope_type, item.scope_id)
    for recipient_id in _scope_recipients(db, item.scope_type, item.scope_id):
        _notify_user(db, recipient_id, "Community event", item.title, "events")
    db.commit()
    return item


@router.post("/events", status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not scope_exists(db, payload.scope_type, payload.scope_id):
        raise HTTPException(status_code=404, detail="Event scope not found.")
    _require_manage_scope(db, user, payload.scope_type, payload.scope_id)
    if payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Event end must be after event start.")
    item = CommunityEvent(organizer_id=user.id, **payload.model_dump(), is_published=False)
    db.add(item)
    db.flush()
    _audit(db, user, "event.created", "event", item.id, item.scope_type, item.scope_id)
    db.commit()
    db.refresh(item)
    return item


@router.post("/groups", status_code=201)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not scope_exists(db, payload.scope_type, payload.scope_id):
        raise HTTPException(status_code=404, detail="Group scope not found.")
    _require_manage_scope(db, user, payload.scope_type, payload.scope_id)
    item = CommunityGroup(
        name=payload.name,
        description=payload.description,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    db.add(GroupMembership(group_id=item.id, user_id=user.id, role="leader"))
    _audit(db, user, "group.created", "group", item.id, item.scope_type, item.scope_id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/groups/mine")
def my_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(CommunityGroup)
        .join(GroupMembership, GroupMembership.group_id == CommunityGroup.id)
        .filter(GroupMembership.user_id == user.id, CommunityGroup.is_active.is_(True))
        .order_by(CommunityGroup.name)
        .all()
    )


@router.get("/groups")
def browse_groups(
    scope_type: Literal["diocese", "parish"],
    scope_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_member_scope(db, user, scope_type, scope_id)
    return db.query(CommunityGroup).filter(
        CommunityGroup.scope_type == scope_type,
        CommunityGroup.scope_id == scope_id,
        CommunityGroup.is_active.is_(True),
    ).order_by(CommunityGroup.name).limit(300).all()


@router.post("/groups/{group_id}/join")
def join_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(CommunityGroup).filter(
        CommunityGroup.id == group_id,
        CommunityGroup.is_active.is_(True),
    ).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    _require_member_scope(db, user, group.scope_type, group.scope_id)
    existing = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user.id,
    ).first()
    if existing:
        return {"group_id": group_id, "status": "joined"}
    db.add(GroupMembership(group_id=group_id, user_id=user.id))
    db.flush()
    conversations = db.query(CommunityConversation).filter(
        CommunityConversation.scope_type == "group",
        CommunityConversation.scope_id == group_id,
        CommunityConversation.is_active.is_(True),
    ).all()
    for conversation in conversations:
        db.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
            )
        )
    db.commit()
    return {"group_id": group_id, "status": "joined"}


@router.delete("/groups/{group_id}/membership")
def leave_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = db.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user.id,
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Group membership not found.")
    db.delete(membership)
    db.query(ConversationMember).join(
        CommunityConversation,
        CommunityConversation.id == ConversationMember.conversation_id,
    ).filter(
        ConversationMember.user_id == user.id,
        CommunityConversation.scope_type == "group",
        CommunityConversation.scope_id == group_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"group_id": group_id, "status": "left"}


@router.post("/prayer-intentions", status_code=201)
def create_prayer_intention(
    payload: PrayerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    parish_id = user.parish_id if payload.visibility in {"parish", "diocese"} else None
    parish = db.query(Parish).filter(Parish.id == parish_id).first() if parish_id else None
    if payload.visibility in {"parish", "diocese"} and parish is None:
        raise HTTPException(status_code=400, detail="Select a parish before sharing this intention.")
    if parish_id is not None:
        _require_member_scope(db, user, "parish", parish_id)
    if payload.visibility == "parish":
        diocese_id = None
    elif payload.visibility == "diocese":
        diocese_id = parish.diocese_id
    else:
        diocese_id = None
    item = PrayerIntention(
        user_id=user.id,
        intention=payload.intention,
        visibility=payload.visibility,
        parish_id=parish_id if payload.visibility == "parish" else None,
        diocese_id=diocese_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "intention": item.intention, "visibility": item.visibility}


@router.get("/prayer-intentions")
def list_prayer_intentions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    parish = db.query(Parish).filter(Parish.id == user.parish_id).first() if user.parish_id else None
    filters = [
        PrayerIntention.user_id == user.id,
        PrayerIntention.visibility == "public",
    ]
    if user.parish_id and user_belongs_to_scope(db, user, "parish", user.parish_id):
        filters.append(
            (PrayerIntention.visibility == "parish")
            & (PrayerIntention.parish_id == user.parish_id)
        )
    if parish and parish.diocese_id and user_belongs_to_scope(
        db, user, "diocese", parish.diocese_id
    ):
        filters.append(
            (PrayerIntention.visibility == "diocese")
            & (PrayerIntention.diocese_id == parish.diocese_id)
        )
    items = db.query(PrayerIntention).filter(
        PrayerIntention.is_active.is_(True),
        or_(*filters),
    ).order_by(PrayerIntention.created_at.desc()).limit(300).all()
    return [
        {
            "id": item.id,
            "intention": item.intention,
            "visibility": item.visibility,
            "created_at": item.created_at,
            "is_mine": item.user_id == user.id,
        }
        for item in items
    ]


@router.post("/conversations", status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_member_scope(db, user, payload.scope_type, payload.scope_id)
    group_id = payload.scope_id if payload.scope_type == "group" else None
    if group_id is not None:
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == group_id,
            CommunityGroup.is_active.is_(True),
        ).first()
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found.")
    else:
        existing = db.query(CommunityConversation).filter(
            CommunityConversation.scope_type == "parish",
            CommunityConversation.scope_id == payload.scope_id,
            CommunityConversation.is_active.is_(True),
        ).first()
        if existing:
            _conversation_for_member(db, existing.id, user)
            return existing
    item = CommunityConversation(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        group_id=group_id,
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    if group_id is None:
        member_ids = [user.id]
    else:
        member_ids = [
            row[0] for row in db.query(GroupMembership.user_id).filter(
                GroupMembership.group_id == group_id
            ).all()
        ]
    for member_id in set(member_ids):
        db.add(ConversationMember(conversation_id=item.id, user_id=member_id))
    db.commit()
    db.refresh(item)
    return item


def _conversation_for_member(db: Session, conversation_id: int, user: User):
    conversation = db.query(CommunityConversation).filter(
        CommunityConversation.id == conversation_id,
        CommunityConversation.is_active.is_(True),
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    _require_member_scope(db, user, conversation.scope_type, conversation.scope_id)
    membership = db.query(ConversationMember.id).filter(
        ConversationMember.conversation_id == conversation.id,
        ConversationMember.user_id == user.id,
    ).first()
    if membership is None:
        if conversation.scope_type != "parish":
            raise HTTPException(status_code=404, detail="Conversation not found.")
        db.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
            )
        )
        db.commit()
    return conversation


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversations = (
        db.query(CommunityConversation)
        .filter(CommunityConversation.is_active.is_(True))
        .order_by(CommunityConversation.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        item for item in conversations
        if user_belongs_to_scope(db, user, item.scope_type, item.scope_id)
        and (
            item.scope_type == "parish"
            or db.query(ConversationMember.id).filter(
                ConversationMember.conversation_id == item.id,
                ConversationMember.user_id == user.id,
            ).first()
        )
    ]


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _conversation_for_member(db, conversation_id, user)
    query = db.query(CommunityMessage).filter(
        CommunityMessage.conversation_id == conversation_id,
        CommunityMessage.is_deleted.is_(False),
    )
    if before_id is not None:
        query = query.filter(CommunityMessage.id < before_id)
    return query.order_by(CommunityMessage.id.desc()).limit(limit).all()


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def create_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _conversation_for_member(db, conversation_id, user)
    if payload.reply_to_id is not None:
        parent = db.query(CommunityMessage).filter(
            CommunityMessage.id == payload.reply_to_id,
            CommunityMessage.conversation_id == conversation.id,
            CommunityMessage.is_deleted.is_(False),
        ).first()
        if parent is None:
            raise HTTPException(status_code=404, detail="Reply target not found in this conversation.")
    members = [
        row[0] for row in db.query(ConversationMember.user_id).filter(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id != user.id,
        ).all()
    ]
    blocked = db.query(MemberBlock.id).filter(
        or_(
            (MemberBlock.blocker_id == user.id) & MemberBlock.blocked_id.in_(members),
            (MemberBlock.blocked_id == user.id) & MemberBlock.blocker_id.in_(members),
        )
    ).first()
    if blocked:
        raise HTTPException(status_code=403, detail="Messaging is unavailable due to a member block.")
    message = CommunityMessage(
        conversation_id=conversation.id,
        sender_id=user.id,
        reply_to_id=payload.reply_to_id,
        body=payload.body,
    )
    db.add(message)
    for member_id in members:
        member = db.query(User).filter(
            User.id == member_id,
            User.is_active.is_(True),
        ).first()
        if member is not None and user_belongs_to_scope(
            db, member, conversation.scope_type, conversation.scope_id
        ):
            _notify_user(
                db,
                member_id,
                "New community message",
                payload.body[:500],
                "messages",
            )
    db.commit()
    db.refresh(message)
    return message


@router.post("/messages/{message_id}/report", status_code=201)
def report_message(
    message_id: int,
    reason: str = Query(min_length=3, max_length=100),
    description: str = Query(default="", max_length=2000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message = db.query(CommunityMessage).filter(
        CommunityMessage.id == message_id,
        CommunityMessage.is_deleted.is_(False),
    ).first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    _conversation_for_member(db, message.conversation_id, user)
    report = ContentReport(
        reporter_id=user.id,
        resource_type="message",
        resource_id=message.id,
        reason=reason,
        description=description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"report_id": report.id, "status": report.status}


@router.delete("/messages/{message_id}")
def delete_own_message(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message = db.query(CommunityMessage).filter(
        CommunityMessage.id == message_id
    ).with_for_update().first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    _conversation_for_member(db, message.conversation_id, user)
    if message.sender_id != user.id:
        raise HTTPException(status_code=403, detail="You can delete only your own messages.")
    message.is_deleted = True
    _audit(
        db, user, "message.deleted", "message", message.id,
        reason="Deleted by message author.",
    )
    db.commit()
    return {"id": message.id, "status": "deleted"}


@router.post("/messages/{message_id}/reactions", status_code=201)
def react_to_message(
    message_id: int,
    payload: ReactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message = db.query(CommunityMessage).filter(
        CommunityMessage.id == message_id,
        CommunityMessage.is_deleted.is_(False),
    ).first()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    _conversation_for_member(db, message.conversation_id, user)
    item = MessageReaction(
        message_id=message.id,
        user_id=user.id,
        reaction=payload.reaction,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already added this reaction.")
    db.refresh(item)
    return item


@router.put("/conversations/{conversation_id}/mute")
def mute_conversation(
    conversation_id: int,
    muted: bool,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _conversation_for_member(db, conversation_id, user)
    membership = db.query(ConversationMember).filter(
        ConversationMember.conversation_id == conversation_id,
        ConversationMember.user_id == user.id,
    ).first()
    membership.is_muted = muted
    db.commit()
    return {"conversation_id": conversation_id, "muted": muted}


@router.post("/members/block", status_code=201)
def block_member(
    payload: BlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.user_id == user.id:
        raise HTTPException(status_code=422, detail="You cannot block your own account.")
    if not db.query(User.id).filter(User.id == payload.user_id, User.is_active.is_(True)).first():
        raise HTTPException(status_code=404, detail="Member not found.")
    existing = db.query(MemberBlock).filter(
        MemberBlock.blocker_id == user.id,
        MemberBlock.blocked_id == payload.user_id,
    ).first()
    if existing:
        return {"status": "blocked"}
    db.add(MemberBlock(blocker_id=user.id, blocked_id=payload.user_id))
    db.commit()
    return {"status": "blocked"}


@router.get("/audit")
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "super_admin":
        return db.query(CommunityAuditLog).order_by(
            CommunityAuditLog.created_at.desc()
        ).limit(limit).all()
    assignments = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user.id,
        RoleAssignment.role.in_(["parish_admin", "diocesan_admin"]),
        RoleAssignment.is_active.is_(True),
    ).all()
    allowed: set[tuple[str, int | None]] = set()
    for assignment in assignments:
        allowed.add((assignment.scope_type, assignment.scope_id))
        if assignment.scope_type == "diocese":
            parish_ids = db.query(Parish.id).filter(
                Parish.diocese_id == assignment.scope_id
            ).all()
            deanery_ids = db.query(Deanery.id).filter(
                Deanery.diocese_id == assignment.scope_id
            ).all()
            allowed.update(("parish", item[0]) for item in parish_ids)
            allowed.update(("deanery", item[0]) for item in deanery_ids)
    logs = db.query(CommunityAuditLog).order_by(
        CommunityAuditLog.created_at.desc()
    ).limit(limit * 5).all()
    return [
        item for item in logs
        if (item.scope_type, item.scope_id) in allowed
    ][:limit]

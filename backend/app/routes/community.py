from datetime import datetime, timedelta, timezone
import hmac
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, func, or_
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
    SuggestionReply,
)
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.notification import Notification
from app.models.report import ContentReport
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services.authorization import (
    can_manage_community_scope,
    can_moderate_community_scope,
    can_review_role_request,
    moderation_scope_ids,
    scope_exists,
    user_belongs_to_scope,
)
from app.services import rate_limit

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
# The project already shipped its own suggestion vocabulary, so it is preserved
# rather than replaced: submitted/under_review/in_discussion/accepted/
# implemented/declined/archived keep their meaning and their stored values.
# Two states the workflow genuinely lacked are added additively:
# "needs_information" (clarification requested) and "escalated" (raised beyond
# the parish). What was missing is a server-side state machine: before this, any
# permitted status could jump to any other, so a moderator could move a fresh
# suggestion straight to "implemented" without review. Terminal states accept no
# further transitions.
SUGGESTION_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {
        "under_review", "needs_information", "in_discussion",
        "accepted", "declined", "escalated", "archived",
    },
    "under_review": {
        "needs_information", "in_discussion", "accepted",
        "declined", "escalated", "archived",
    },
    "in_discussion": {
        "under_review", "needs_information", "accepted",
        "declined", "escalated", "archived",
    },
    "needs_information": {
        "under_review", "in_discussion", "accepted",
        "declined", "escalated", "archived",
    },
    "accepted": {"in_discussion", "implemented", "declined", "escalated", "archived"},
    "escalated": {
        "under_review", "in_discussion", "accepted",
        "implemented", "declined", "archived",
    },
    "implemented": set(),
    "declined": set(),
    "archived": set(),
}
SUGGESTION_TERMINAL_STATUSES = {"implemented", "declined", "archived"}
SUGGESTION_STATUSES = set(SUGGESTION_TRANSITIONS)
# Statuses that require an explicit explanation so the submitter is not left
# guessing why nothing is happening.
SUGGESTION_STATUSES_REQUIRING_NOTE = {
    "needs_information",
    "declined",
    "archived",
}
# Report categories offered to members. The value is stored in
# ContentReport.category; ContentReport.reason stays free text for context.
REPORT_CATEGORIES = {
    "spam",
    "harassment",
    "abusive_language",
    "inappropriate_content",
    "misleading_information",
    "suspicious_activity",
    "copyright",
    "other",
}
COMMUNITY_RULES = (
    "Share in charity and truth. Be respectful of every parish member, "
    "especially in matters of faith. Do not share Mass intentions, private "
    "confessions, or contact details without permission. Keep corrections to "
    "readings, saints, and music factual and sourced. Report anything that "
    "concerns you and a moderator will review it."
)


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


class DirectConversationCreate(BaseModel):
    user_id: int = Field(gt=0)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    reply_to_id: int | None = Field(default=None, gt=0)


class ReactionCreate(BaseModel):
    reaction: str = Field(min_length=1, max_length=20)


class BlockCreate(BaseModel):
    user_id: int = Field(gt=0)


class MessageEdit(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        # min_length alone accepts "   ", which would let an edit erase a message
        # while leaving an empty row behind for every other member to read.
        stripped = value.strip()
        if not stripped:
            raise ValueError("A message cannot be edited to be blank.")
        return stripped


class ReactionRemove(BaseModel):
    reaction: str = Field(min_length=1, max_length=20)


class SuggestionReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    # Internal notes are visible only to authorized administrators in scope.
    is_internal: bool = False


class MessageReportCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=2000)


def _conversation_parish_id(db: Session, conversation_id: int) -> int | None:
    """The parish owning a conversation, or None for direct/group threads."""
    conversation = db.query(CommunityConversation).filter(
        CommunityConversation.id == conversation_id
    ).first()
    if conversation is None:
        return None
    if conversation.scope_type == "parish":
        return conversation.scope_id
    if conversation.scope_type == "group" and conversation.group_id is not None:
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == conversation.group_id
        ).first()
        if group is not None and group.scope_type == "parish":
            return group.scope_id
        return None
    return None


def conversation_is_parish_scope(db: Session, conversation_id: int) -> bool:
    return _conversation_parish_id(db, conversation_id) is not None


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


def _recent_notification_titles(db: Session, user_id: int, title: str, window_minutes: int) -> int:
    """Count identical notification titles emitted to a user in a recent window."""
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == user_id,
            Notification.title == title,
            Notification.created_at >= since,
        )
        .scalar()
        or 0
    )


def _notify_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    category: str,
    throttle: tuple[int, int] | None = None,
) -> bool:
    """Queue a notification unless the user opted out or is being flooded.

    ``throttle`` is ``(max_identical, window_minutes)``. A parish-wide
    conversation notifies every member on every message, which for an active
    parish means hundreds of rows a day per member; collapsing identical recent
    titles keeps the notification list meaningful without dropping the signal
    that something happened. Returns True when a row was queued.
    """
    preference = db.query(CommunityNotificationPreference).filter(
        CommunityNotificationPreference.user_id == user_id
    ).first()
    if preference is not None and not getattr(preference, category):
        return False
    if throttle is not None and user_id > 0:
        max_identical, window_minutes = throttle
        if _recent_notification_titles(db, user_id, title, window_minutes) >= max_identical:
            return False
    db.add(Notification(user_id=user_id, title=title, body=body))
    return True


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


@router.get("/header")
def community_header(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Identity card for the caller's parish community.

    Every value is derived from the authenticated user's own trusted membership,
    so there is no scope parameter a client could tamper with. Members with no
    active parish membership get ``community: null`` plus the reason, which lets
    the UI explain why the conversation is unavailable instead of showing an
    empty feed that looks broken.
    """
    active_membership = (
        db.query(ParishMembership)
        .filter(
            ParishMembership.user_id == user.id,
            ParishMembership.status == "active",
        )
        .order_by(ParishMembership.requested_at.desc())
        .first()
    )
    base = {
        "community": None,
        "parish_membership_status": active_membership.status if active_membership else None,
        "rules": COMMUNITY_RULES,
    }
    if active_membership is None:
        base["unavailable_reason"] = (
            "Your parish membership is not active yet. "
            "An administrator must approve it before you can join the parish community."
        )
        return base

    parish = db.query(Parish).filter(Parish.id == active_membership.parish_id).first()
    if parish is None or getattr(parish, "is_active", True) is False:
        base["unavailable_reason"] = "This parish is not currently active."
        return base

    diocese = (
        db.query(Diocese).filter(Diocese.id == parish.diocese_id).first()
        if parish.diocese_id
        else None
    )
    deanery = (
        db.query(Deanery).filter(Deanery.id == parish.deanery_id).first()
        if parish.deanery_id
        else None
    )
    member_count = (
        db.query(func.count(ParishMembership.id))
        .filter(
            ParishMembership.parish_id == parish.id,
            ParishMembership.status == "active",
        )
        .scalar()
        or 0
    )
    conversation = (
        db.query(CommunityConversation)
        .filter(
            CommunityConversation.conversation_type == "scope",
            CommunityConversation.scope_type == "parish",
            CommunityConversation.scope_id == parish.id,
            CommunityConversation.is_active.is_(True),
        )
        .first()
    )
    my_roles = [
        {
            "role": assignment.role,
            "scope_type": assignment.scope_type,
            "scope_id": assignment.scope_id,
            "ministry": assignment.ministry,
        }
        for assignment in db.query(RoleAssignment).filter(
            RoleAssignment.user_id == user.id,
            RoleAssignment.scope_type == "parish",
            RoleAssignment.scope_id == parish.id,
            RoleAssignment.is_active.is_(True),
        ).all()
    ]
    base["community"] = {
        "parish_id": parish.id,
        "parish_name": parish.name,
        "parish_code": parish.code,
        "diocese_id": parish.diocese_id,
        "diocese_name": diocese.name if diocese else None,
        "deanery_id": parish.deanery_id,
        "deanery_name": deanery.name if deanery else None,
        "member_count": member_count,
        "description": (
            f"{parish.name} parish community"
            + (f", {diocese.name}" if diocese else "")
        ),
        "rules": COMMUNITY_RULES,
        "conversation_id": conversation.id if conversation else None,
        "my_roles": my_roles,
        "can_moderate": can_moderate_community_scope(db, user, "parish", parish.id),
        "can_manage": can_manage_community_scope(db, user, "parish", parish.id),
    }
    return base


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
    rate_limit.consume("community.suggestion", user.id, rate_limit.SUGGESTION_SUBMIT)
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
    # Route to administration by organizational scope rather than making the
    # member pick an administrator. Only administrators who actually hold that
    # scope are notified, so a parish suggestion never reaches another parish.
    recipients = _suggestion_administrators(db, payload.scope_type, payload.scope_id)
    item.assigned_to = recipients[0] if recipients else None
    for administrator_id in recipients:
        _notify_user(
            db,
            administrator_id,
            "New parish suggestion",
            f"A {payload.category} suggestion was submitted in your scope.",
            "role_requests",
        )
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
        "assigned_to": item.assigned_to,
        "created_at": item.created_at,
    }


def _suggestion_administrators(
    db: Session, scope_type: str, scope_id: int
) -> list[int]:
    """Administrator ids authorized to handle a suggestion in this scope."""
    if scope_type not in {"parish", "diocese"}:
        return []
    administrators: list[int] = []
    for person in db.query(User).filter(User.is_active.is_(True)).all():
        if can_manage_community_scope(db, person, scope_type, scope_id):
            administrators.append(person.id)
    return administrators


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
    """The review queue for the caller's scopes.

    The query is constrained to authorized scopes in SQL. Loading every open
    suggestion in the platform and filtering afterwards would both pull other
    parishes' text into the request and make the response cost grow with total
    platform volume.
    """
    query = db.query(CommunitySuggestion).filter(
        CommunitySuggestion.status.notin_(SUGGESTION_TERMINAL_STATUSES)
    )
    scopes = moderation_scope_ids(db, user)
    if scopes:
        conditions = [
            (CommunitySuggestion.scope_type == scope_type)
            & (CommunitySuggestion.scope_id == scope_id)
            for scope_type, scope_id in scopes
        ]
        query = query.filter(or_(*conditions))
    elif scopes is not None:
        # Holds moderator roles, but in no scope this queue covers.
        return []
    items = query.order_by(CommunitySuggestion.created_at.asc()).limit(200).all()
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
            "assigned_to": item.assigned_to,
            "escalated_at": item.escalated_at,
            "created_at": item.created_at,
        }
        for item in items
    ]


def _suggestion_for_participant(
    db: Session, suggestion_id: int, user: User
) -> tuple[CommunitySuggestion, bool]:
    """Fetch a suggestion the caller is entitled to see.

    Returns the suggestion and whether the caller administers its scope.
    Submitters keep access to their own suggestion regardless of role so they can
    follow replies; every other reader must hold scope authority.
    """
    suggestion = db.query(CommunitySuggestion).filter(
        CommunitySuggestion.id == suggestion_id
    ).first()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    manages = can_manage_community_scope(
        db, user, suggestion.scope_type, suggestion.scope_id
    )
    if not manages and suggestion.submitter_id != user.id:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return suggestion, manages


def _require_suggestion_scope(
    db: Session, user: User, suggestion: CommunitySuggestion
) -> None:
    """Guard the suggestion write endpoints.

    This deliberately answers 404 rather than 403, matching
    ``_suggestion_for_participant``. An administrator of one parish must not be
    able to learn that a suggestion with a given id exists in another parish, so
    the two surfaces report the same thing for the same reason.
    """
    if not can_manage_community_scope(
        db, user, suggestion.scope_type, suggestion.scope_id
    ):
        raise HTTPException(status_code=404, detail="Suggestion not found.")


@router.get("/suggestions/{suggestion_id}")
def suggestion_detail(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion, manages = _suggestion_for_participant(db, suggestion_id, user)
    replies = (
        db.query(SuggestionReply)
        .filter(SuggestionReply.suggestion_id == suggestion.id)
        .order_by(SuggestionReply.created_at.asc(), SuggestionReply.id.asc())
        .all()
    )
    visible = [reply for reply in replies if manages or not reply.is_internal]
    submitter_name = None
    if suggestion.submitter_id is not None:
        submitter = db.query(User).filter(User.id == suggestion.submitter_id).first()
        submitter_name = submitter.full_name if submitter else None
    return {
        "id": suggestion.id,
        "category": suggestion.category,
        "body": suggestion.body,
        "scope_type": suggestion.scope_type,
        "scope_id": suggestion.scope_id,
        "status": suggestion.status,
        "review_note": suggestion.review_note,
        "is_anonymous": suggestion.is_anonymous,
        "submitter_id": None if suggestion.is_anonymous else suggestion.submitter_id,
        "submitter_name": None if suggestion.is_anonymous else submitter_name,
        "assigned_to": suggestion.assigned_to,
        "resolved_at": suggestion.resolved_at,
        "escalated_at": suggestion.escalated_at,
        "created_at": suggestion.created_at,
        "replies": [
            {
                "id": reply.id,
                "author_id": reply.author_id,
                "body": reply.body,
                # The submitter is never shown that an internal note exists.
                "is_internal": reply.is_internal if manages else None,
                "created_at": reply.created_at,
            }
            for reply in visible
        ],
        "can_manage": manages,
    }


@router.post("/suggestions/{suggestion_id}/replies", status_code=201)
def reply_to_suggestion(
    suggestion_id: int,
    payload: SuggestionReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Administrator reply on a suggestion.

    Public replies notify the submitter. Internal notes stay inside the
    moderation surface so private administrative discussion is never exposed to
    the member.
    """
    suggestion = db.query(CommunitySuggestion).filter(
        CommunitySuggestion.id == suggestion_id
    ).with_for_update().first()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    _require_suggestion_scope(db, user, suggestion)
    rate_limit.consume("community.suggestion.reply", user.id, rate_limit.SUGGESTION_REPLY)
    reply = SuggestionReply(
        suggestion_id=suggestion.id,
        author_id=user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(reply)
    if suggestion.assigned_to is None:
        suggestion.assigned_to = user.id
    if not payload.is_internal and suggestion.submitter_id is not None:
        _notify_user(
            db,
            suggestion.submitter_id,
            "Reply to your suggestion",
            payload.body[:500],
            "role_requests",
        )
    _audit(
        db, user, "suggestion.replied", "suggestion", suggestion.id,
        suggestion.scope_type, suggestion.scope_id,
        "internal note" if payload.is_internal else "reply",
    )
    db.commit()
    db.refresh(reply)
    return {
        "id": reply.id,
        "suggestion_id": reply.suggestion_id,
        "author_id": reply.author_id,
        "is_internal": reply.is_internal,
        "created_at": reply.created_at,
    }


@router.patch("/suggestions/{suggestion_id}")
def update_suggestion(
    suggestion_id: int,
    payload: ReviewStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.status not in SUGGESTION_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid suggestion status.")
    if payload.status in SUGGESTION_STATUSES_REQUIRING_NOTE and not payload.review_note:
        raise HTTPException(
            status_code=422,
            detail="A review note is required when moving a suggestion to this status.",
        )
    item = db.query(CommunitySuggestion).filter(
        CommunitySuggestion.id == suggestion_id
    ).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    _require_suggestion_scope(db, user, item)
    # Server-side transition validation: a suggestion cannot skip straight from
    # "submitted" to "implemented", and a closed suggestion cannot be reopened.
    permitted = SUGGESTION_TRANSITIONS.get(item.status, set())
    if payload.status not in permitted:
        if item.status in SUGGESTION_TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This suggestion is already closed as '{item.status}' "
                    "and cannot change status."
                ),
            )
        raise HTTPException(
            status_code=409,
            detail=(
                f"A suggestion in '{item.status}' cannot move to "
                f"'{payload.status}'."
            ),
        )
    previous_status = item.status
    item.status = payload.status
    item.reviewer_id = user.id
    item.review_note = payload.review_note
    if item.assigned_to is None:
        item.assigned_to = user.id
    now = datetime.now(timezone.utc)
    if payload.status in SUGGESTION_TERMINAL_STATUSES:
        item.resolved_at = now
    if payload.status == "escalated":
        item.escalated_at = now
    _audit(
        db, user, f"suggestion.{payload.status}", "suggestion", item.id,
        item.scope_type, item.scope_id,
        payload.review_note or f"{previous_status} -> {payload.status}",
    )
    if item.submitter_id is not None:
        _notify_user(
            db,
            item.submitter_id,
            "Suggestion updated",
            f"Your suggestion moved from {previous_status} to {payload.status}.",
            "role_requests",
        )
    db.commit()
    return {
        "id": item.id,
        "status": item.status,
        "previous_status": previous_status,
        "review_note": item.review_note,
        "scope_type": item.scope_type,
        "scope_id": item.scope_id,
        "resolved_at": item.resolved_at,
        "escalated_at": item.escalated_at,
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
        conversation_type="scope",
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
    membership = db.query(ConversationMember).filter(
        ConversationMember.conversation_id == conversation.id,
        ConversationMember.user_id == user.id,
    ).first()
    if conversation.conversation_type == "direct":
        if membership is None:
            raise HTTPException(
                status_code=403,
                detail="You are not a participant in this conversation.",
            )
        return conversation
    _require_member_scope(db, user, conversation.scope_type, conversation.scope_id)
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


def _direct_key(user_id: int, other_id: int) -> str:
    low, high = sorted((user_id, other_id))
    return f"{low}:{high}"


def _conversation_unread_count(
    db: Session, conversation_id: int, membership: ConversationMember, user_id: int
) -> int:
    query = db.query(CommunityMessage.id).filter(
        CommunityMessage.conversation_id == conversation_id,
        CommunityMessage.is_deleted.is_(False),
        CommunityMessage.sender_id != user_id,
    )
    if membership.last_read_message_id is not None:
        query = query.filter(CommunityMessage.id > membership.last_read_message_id)
    return query.count()


def _conversation_summary(
    db: Session, conversation: CommunityConversation, user: User
) -> dict:
    membership = db.query(ConversationMember).filter(
        ConversationMember.conversation_id == conversation.id,
        ConversationMember.user_id == user.id,
    ).first()
    last_message = (
        db.query(CommunityMessage)
        .filter(
            CommunityMessage.conversation_id == conversation.id,
            CommunityMessage.is_deleted.is_(False),
        )
        .order_by(CommunityMessage.id.desc())
        .first()
    )
    summary = {
        "id": conversation.id,
        "conversation_type": conversation.conversation_type,
        "scope_type": conversation.scope_type,
        "scope_id": conversation.scope_id,
        "group_id": conversation.group_id,
        "created_by": conversation.created_by,
        "created_at": conversation.created_at,
        "unread_count": _conversation_unread_count(
            db, conversation.id, membership, user.id
        ) if membership else 0,
        "is_muted": membership.is_muted if membership else False,
        "last_message": {
            "id": last_message.id,
            "sender_id": last_message.sender_id,
            "body": last_message.body,
            "created_at": last_message.created_at,
        } if last_message else None,
    }
    if conversation.conversation_type == "direct":
        other_id = (
            db.query(ConversationMember.user_id)
            .filter(
                ConversationMember.conversation_id == conversation.id,
                ConversationMember.user_id != user.id,
            )
            .scalar()
        )
        other = db.query(User).filter(User.id == other_id).first() if other_id else None
        summary["participant"] = {
            "id": other.id,
            "full_name": other.full_name,
        } if other else None
    return summary


def _mark_conversation_read(
    db: Session, conversation_id: int, user: User, up_to_message_id: int | None = None
) -> None:
    membership = db.query(ConversationMember).filter(
        ConversationMember.conversation_id == conversation_id,
        ConversationMember.user_id == user.id,
    ).first()
    if membership is None:
        return
    if up_to_message_id is None:
        up_to_message_id = (
            db.query(CommunityMessage.id)
            .filter(CommunityMessage.conversation_id == conversation_id)
            .order_by(CommunityMessage.id.desc())
            .limit(1)
            .scalar()
        )
    if up_to_message_id is None:
        return
    if (
        membership.last_read_message_id is None
        or up_to_message_id > membership.last_read_message_id
    ):
        membership.last_read_message_id = up_to_message_id
        membership.last_read_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/conversations/direct", status_code=201)
def create_direct_conversation(
    payload: DirectConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.user_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot start a conversation with yourself.",
        )
    rate_limit.consume(
        "community.conversation.create", user.id, rate_limit.CONVERSATION_CREATE
    )
    other = db.query(User).filter(
        User.id == payload.user_id,
        User.is_active.is_(True),
    ).first()
    if other is None:
        raise HTTPException(status_code=404, detail="User not found.")
    blocked = db.query(MemberBlock.id).filter(
        or_(
            (MemberBlock.blocker_id == user.id) & (MemberBlock.blocked_id == other.id),
            (MemberBlock.blocker_id == other.id) & (MemberBlock.blocked_id == user.id),
        )
    ).first()
    if blocked:
        raise HTTPException(
            status_code=403,
            detail="Messaging is unavailable due to a member block.",
        )
    key = _direct_key(user.id, other.id)
    conversation = db.query(CommunityConversation).filter(
        CommunityConversation.direct_key == key,
        CommunityConversation.is_active.is_(True),
    ).first()
    if conversation is None:
        conversation = CommunityConversation(
            conversation_type="direct",
            scope_type=None,
            scope_id=None,
            direct_key=key,
            created_by=user.id,
        )
        db.add(conversation)
        db.flush()
        for member_id in (user.id, other.id):
            db.add(
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=member_id,
                )
            )
        db.commit()
        db.refresh(conversation)
    return _conversation_summary(db, conversation, user)


@router.get("/members")
def search_members(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rate_limit.consume("community.member.search", user.id, rate_limit.MEMBER_SEARCH)
    active_parish_ids = [
        row[0]
        for row in db.query(ParishMembership.parish_id).filter(
            ParishMembership.user_id == user.id,
            ParishMembership.status == "active",
        ).all()
    ]
    if not active_parish_ids:
        return []
    shared_member_ids = {
        row[0]
        for row in db.query(ParishMembership.user_id).filter(
            ParishMembership.parish_id.in_(active_parish_ids),
            ParishMembership.status == "active",
        ).distinct().all()
    }
    shared_member_ids.discard(user.id)
    if not shared_member_ids:
        return []
    blocked_ids = {
        row[0]
        for row in db.query(MemberBlock.blocked_id).filter(
            MemberBlock.blocker_id == user.id,
            MemberBlock.blocked_id.in_(shared_member_ids),
        ).all()
    } | {
        row[0]
        for row in db.query(MemberBlock.blocker_id).filter(
            MemberBlock.blocked_id == user.id,
            MemberBlock.blocker_id.in_(shared_member_ids),
        ).all()
    }
    candidate_ids = shared_member_ids - blocked_ids
    if not candidate_ids:
        return []
    query = db.query(User).filter(
        User.id.in_(candidate_ids),
        User.is_active.is_(True),
    )
    if q:
        query = query.filter(User.full_name.ilike(f"%{q}%"))
    return [
        {
            "id": member.id,
            "full_name": member.full_name,
            "parish_id": member.parish_id,
        }
        for member in query.order_by(User.full_name).limit(limit).all()
    ]


def _blocked_ids_between(db: Session, user_id: int, other_ids: set[int]) -> set[int]:
    """Subset of ``other_ids`` that the caller has blocked, or who blocked them."""
    if not other_ids:
        return set()
    blocked_by_me = {
        row[0]
        for row in db.query(MemberBlock.blocked_id)
        .filter(
            MemberBlock.blocker_id == user_id,
            MemberBlock.blocked_id.in_(other_ids),
        )
        .all()
    }
    blocked_me = {
        row[0]
        for row in db.query(MemberBlock.blocker_id)
        .filter(
            MemberBlock.blocked_id == user_id,
            MemberBlock.blocker_id.in_(other_ids),
        )
        .all()
    }
    return blocked_by_me | blocked_me


def _blocked_direct_conversation_ids(
    db: Session, user: User, direct_ids: set[int]
) -> set[int]:
    """Direct conversations whose other participant is blocked either way.

    Resolved with two queries regardless of how many threads are involved, so
    the caller can drop these ids before paginating.
    """
    if not direct_ids:
        return set()
    peer_by_conversation: dict[int, int] = {}
    for row in db.query(
        ConversationMember.conversation_id, ConversationMember.user_id
    ).filter(
        ConversationMember.conversation_id.in_(direct_ids),
        ConversationMember.user_id != user.id,
    ).all():
        peer_by_conversation[row[0]] = row[1]
    if not peer_by_conversation:
        return set()
    blocked = _blocked_ids_between(db, user.id, set(peer_by_conversation.values()))
    if not blocked:
        return set()
    return {
        conversation_id
        for conversation_id, peer_id in peer_by_conversation.items()
        if peer_id in blocked
    }


def _visible_conversation_ids(db: Session, user: User) -> tuple[list[int], set[int]]:
    """Conversation ids the caller may see, resolved in SQL rather than in Python.

    Returning ids first means the conversation query itself can be constrained to
    the caller's own data. The previous implementation loaded every conversation
    in the table and filtered afterwards, which both leaked cross-parish rows
    into the request and made the response cost grow with the size of the whole
    community table.
    """
    member_conversation_ids = [
        row[0]
        for row in db.query(ConversationMember.conversation_id).filter(
            ConversationMember.user_id == user.id
        ).all()
    ]
    direct_ids = [
        row[0]
        for row in db.query(CommunityConversation.id)
        .filter(
            CommunityConversation.conversation_type == "direct",
            CommunityConversation.is_active.is_(True),
            CommunityConversation.id.in_(member_conversation_ids or [0]),
        )
        .all()
    ]

    parish_ids = [
        row[0]
        for row in db.query(ParishMembership.parish_id).filter(
            ParishMembership.user_id == user.id,
            ParishMembership.status == "active",
        ).all()
    ]
    # Group threads additionally require that the group sits inside a scope the
    # member actually belongs to, not merely that they joined the group row.
    # Every candidate group is checked against the same three sets that
    # ``user_belongs_to_scope`` consults, so the whole decision is one query
    # instead of two per group.
    joined_groups = db.query(
        CommunityGroup.id, CommunityGroup.scope_type, CommunityGroup.scope_id
    ).join(
        GroupMembership, GroupMembership.group_id == CommunityGroup.id
    ).filter(
        GroupMembership.user_id == user.id,
        CommunityGroup.is_active.is_(True),
    )
    group_ids = [tuple(row) for row in joined_groups.all()]
    diocese_ids: set[int] = set()
    deanery_ids: set[int] = set()
    if parish_ids:
        hierarchy = {
            row[0]: (row[1], row[2])
            for row in db.query(Parish.id, Parish.diocese_id, Parish.deanery_id)
            .filter(Parish.id.in_(parish_ids))
            .all()
        }
        diocese_ids = {
            diocese_id for diocese_id, _ in hierarchy.values() if diocese_id
        }
        deanery_ids = {
            deanery_id for _, deanery_id in hierarchy.values() if deanery_id
        }

    scope_group_ids: list[int] = []
    for group_id, group_scope_type, group_scope_id in group_ids:
        if group_scope_type == "parish":
            if group_scope_id in parish_ids:
                scope_group_ids.append(group_id)
        elif group_scope_type == "diocese":
            if group_scope_id in diocese_ids:
                scope_group_ids.append(group_id)
        elif group_scope_type == "deanery":
            if group_scope_id in deanery_ids:
                scope_group_ids.append(group_id)

    scope_ids: list[int] = []
    if parish_ids:
        scope_ids.extend(
            row[0]
            for row in db.query(CommunityConversation.id)
            .filter(
                CommunityConversation.conversation_type == "scope",
                CommunityConversation.scope_type == "parish",
                CommunityConversation.scope_id.in_(parish_ids),
                CommunityConversation.is_active.is_(True),
            )
            .all()
        )
    if scope_group_ids:
        group_conversation_ids = [
            row[0]
            for row in db.query(CommunityConversation.id)
            .filter(
                CommunityConversation.conversation_type == "scope",
                CommunityConversation.scope_type == "group",
                CommunityConversation.scope_id.in_(scope_group_ids),
                CommunityConversation.is_active.is_(True),
            )
            .all()
        ]
        # Non-parish scope threads stay restricted to explicit members.
        joined = {
            row[0]
            for row in db.query(ConversationMember.conversation_id).filter(
                ConversationMember.user_id == user.id,
                ConversationMember.conversation_id.in_(group_conversation_ids or [0]),
            ).all()
        }
        scope_ids.extend(joined)

    visible = list({*direct_ids, *scope_ids})
    return visible, set(direct_ids)


def _conversation_summaries_bulk(
    db: Session,
    conversations: list[CommunityConversation],
    user: User,
    excluded_direct_participants: set[int] | None = None,
) -> list[dict]:
    """Build conversation summaries in a fixed number of queries.

    The per-conversation version issued three or four queries each, so a member
    with a busy parish feed paid hundreds of round trips per screen load.
    """
    if not conversations:
        return []
    conversation_ids = [conversation.id for conversation in conversations]

    memberships = {
        membership.conversation_id: membership
        for membership in db.query(ConversationMember).filter(
            ConversationMember.conversation_id.in_(conversation_ids),
            ConversationMember.user_id == user.id,
        ).all()
    }

    last_message_ids = {
        row[0]: row[1]
        for row in db.query(
            CommunityMessage.conversation_id,
            func.max(CommunityMessage.id),
        )
        .filter(
            CommunityMessage.conversation_id.in_(conversation_ids),
            CommunityMessage.is_deleted.is_(False),
        )
        .group_by(CommunityMessage.conversation_id)
        .all()
    }
    last_messages: dict[int, CommunityMessage] = {}
    if last_message_ids:
        last_messages = {
            message.id: message
            for message in db.query(CommunityMessage)
            .filter(CommunityMessage.id.in_(set(last_message_ids.values())))
            .all()
        }

    unread_conditions = []
    for conversation_id in conversation_ids:
        membership = memberships.get(conversation_id)
        condition = CommunityMessage.conversation_id == conversation_id
        if membership is not None and membership.last_read_message_id is not None:
            condition = and_(condition, CommunityMessage.id > membership.last_read_message_id)
        unread_conditions.append(condition)
    unread_counts = {
        row[0]: row[1]
        for row in db.query(
            CommunityMessage.conversation_id,
            func.count(CommunityMessage.id),
        )
        .filter(
            CommunityMessage.conversation_id.in_(conversation_ids),
            CommunityMessage.is_deleted.is_(False),
            CommunityMessage.sender_id != user.id,
            or_(*unread_conditions),
        )
        .group_by(CommunityMessage.conversation_id)
        .all()
    }

    direct_ids = [
        conversation.id
        for conversation in conversations
        if conversation.conversation_type == "direct"
    ]
    participants: dict[int, int] = {}
    if direct_ids:
        for row in db.query(
            ConversationMember.conversation_id, ConversationMember.user_id
        ).filter(
            ConversationMember.conversation_id.in_(direct_ids),
            ConversationMember.user_id != user.id,
        ).all():
            participants[row[0]] = row[1]

    participant_profiles: dict[int, User] = {}
    if participants:
        participant_profiles = {
            person.id: person
            for person in db.query(User)
            .filter(User.id.in_(set(participants.values())))
            .all()
        }

    blocked = (
        _blocked_ids_between(db, user.id, set(participants.values()))
        if participants
        else set()
    )
    hide = excluded_direct_participants or set()

    summaries: list[dict] = []
    for conversation in conversations:
        if (
            conversation.conversation_type == "direct"
            and participants.get(conversation.id) in blocked | hide
        ):
            continue
        membership = memberships.get(conversation.id)
        last_message = last_messages.get(
            last_message_ids.get(conversation.id, 0)
        )
        summary = {
            "id": conversation.id,
            "conversation_type": conversation.conversation_type,
            "scope_type": conversation.scope_type,
            "scope_id": conversation.scope_id,
            "group_id": conversation.group_id,
            "created_by": conversation.created_by,
            "created_at": conversation.created_at,
            "unread_count": unread_counts.get(conversation.id, 0),
            "is_muted": membership.is_muted if membership else False,
            "last_message": {
                "id": last_message.id,
                "sender_id": last_message.sender_id,
                "body": last_message.body,
                "created_at": last_message.created_at,
            } if last_message else None,
        }
        if conversation.conversation_type == "direct":
            other = participant_profiles.get(participants.get(conversation.id, 0))
            summary["participant"] = {
                "id": other.id,
                "full_name": other.full_name,
            } if other else None
        summaries.append(summary)
    return summaries


@router.get("/conversations")
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    visible_ids, direct_ids = _visible_conversation_ids(db, user)
    hidden_direct_ids = _blocked_direct_conversation_ids(db, user, direct_ids)
    if hidden_direct_ids:
        # Excluded before pagination rather than after, so a page is never short
        # because a blocked thread sat inside the requested window.
        visible_ids = [
            conversation_id
            for conversation_id in visible_ids
            if conversation_id not in hidden_direct_ids
        ]
    if not visible_ids:
        return []
    conversations = (
        db.query(CommunityConversation)
        .filter(
            CommunityConversation.id.in_(visible_ids),
            CommunityConversation.is_active.is_(True),
        )
        .order_by(CommunityConversation.created_at.desc(), CommunityConversation.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return _conversation_summaries_bulk(db, conversations, user)


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Single conversation summary, membership-checked.

    Membership is resolved through the same helper the message endpoints use, so
    a guessed id cannot reveal that a conversation exists.
    """
    conversation = _conversation_for_member(db, conversation_id, user)
    summaries = _conversation_summaries_bulk(db, [conversation], user)
    if not summaries:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return summaries[0]


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
    messages = query.order_by(CommunityMessage.id.desc()).limit(limit).all()
    if before_id is None and messages:
        _mark_conversation_read(db, conversation_id, user, messages[0].id)
    return messages


@router.post("/conversations/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _conversation_for_member(db, conversation_id, user)
    _mark_conversation_read(db, conversation_id, user)
    return {"conversation_id": conversation_id, "status": "read"}



@router.post("/conversations/{conversation_id}/messages", status_code=201)
def create_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _conversation_for_member(db, conversation_id, user)
    rate_limit.consume("community.message.send", user.id, rate_limit.MESSAGE_SEND)
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
        if member is not None and (
            conversation.conversation_type == "direct"
            or user_belongs_to_scope(
                db, member, conversation.scope_type, conversation.scope_id
            )
        ):
            _notify_user(
                db,
                member_id,
                "New community message",
                payload.body[:500],
                "messages",
                throttle=(5, 60),
            )
    db.commit()
    db.refresh(message)
    return message


@router.post("/messages/{message_id}/report", status_code=201)
def report_message(
    message_id: int,
    payload: MessageReportCreate,
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
    rate_limit.consume("community.report", user.id, rate_limit.REPORT_SUBMIT)
    if payload.category not in REPORT_CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown report category.")
    if message.sender_id == user.id:
        raise HTTPException(
            status_code=422, detail="You cannot report your own message."
        )
    report = ContentReport(
        reporter_id=user.id,
        resource_type="message",
        resource_id=message.id,
        category=payload.category,
        reason=payload.reason,
        description=payload.description,
        conversation_id=message.conversation_id,
        # Scope is derived from the conversation, never accepted from the client,
        # so a moderator queue cannot be widened by tampering with a request.
        scope_type=(
            "parish"
            if conversation_is_parish_scope(db, message.conversation_id)
            else None
        ),
        scope_id=_conversation_parish_id(db, message.conversation_id),
    )
    db.add(report)
    _audit(
        db, user, "message.reported", "message", message.id,
        reason=f"{payload.category}: {payload.reason}",
    )
    db.commit()
    db.refresh(report)
    return {
        "report_id": report.id,
        "status": report.status,
        "category": report.category,
    }


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
    rate_limit.consume("community.reaction", user.id, rate_limit.REACTION)
    existing = db.query(MessageReaction.id).filter(
        MessageReaction.message_id == message.id,
        MessageReaction.user_id == user.id,
        MessageReaction.reaction == payload.reaction,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already added this reaction.")
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


@router.patch("/messages/{message_id}")
def edit_own_message(
    message_id: int,
    payload: MessageEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edit a message the caller authored.

    Ownership is enforced against the stored ``sender_id`` rather than anything
    client supplied, so swapping the path id cannot reach another member's post.
    Conversation membership is re-checked first so a removed member cannot keep
    editing history they can no longer read.
    """
    message = db.query(CommunityMessage).filter(
        CommunityMessage.id == message_id
    ).with_for_update().first()
    if message is None or message.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found.")
    _conversation_for_member(db, message.conversation_id, user)
    if message.sender_id != user.id:
        raise HTTPException(status_code=403, detail="You can edit only your own messages.")
    message.body = payload.body.strip()
    message.is_edited = True
    message.edited_at = datetime.now(timezone.utc)
    _audit(
        db, user, "message.edited", "message", message.id,
        reason="Edited by message author.",
    )
    db.commit()
    db.refresh(message)
    return message


@router.delete("/messages/{message_id}/reactions")
def remove_reaction(
    message_id: int,
    payload: ReactionRemove,
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
    reaction = db.query(MessageReaction).filter(
        MessageReaction.message_id == message.id,
        MessageReaction.user_id == user.id,
        MessageReaction.reaction == payload.reaction,
    ).first()
    if reaction is None:
        raise HTTPException(status_code=404, detail="Reaction not found.")
    db.delete(reaction)
    db.commit()
    return {"message_id": message.id, "status": "removed"}


@router.get("/messages/{message_id}/reactions")
def list_reactions(
    message_id: int,
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
    reactions = db.query(MessageReaction).filter(
        MessageReaction.message_id == message.id
    ).all()
    counts: dict[str, int] = {}
    for reaction in reactions:
        counts[reaction.reaction] = counts.get(reaction.reaction, 0) + 1
    return {
        "message_id": message.id,
        "counts": counts,
        "mine": [r.reaction for r in reactions if r.user_id == user.id],
    }


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
    rate_limit.consume("community.block", user.id, rate_limit.BLOCK_CHANGE)
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


@router.get("/members/blocks")
def list_blocks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Blocks the caller set, and blocks other members set against the caller.

    Returning both directions lets the UI explain why someone is unreachable
    without leaking anything about accounts outside the caller's own community.
    """
    blocked = [
        {
            "user_id": person.id,
            "full_name": person.full_name,
            "direction": "blocked_by_me",
        }
        for person in db.query(User)
        .join(MemberBlock, MemberBlock.blocked_id == User.id)
        .filter(MemberBlock.blocker_id == user.id, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    ]
    blocked_me = [
        {
            "user_id": person.id,
            "full_name": person.full_name,
            "direction": "blocked_me",
        }
        for person in db.query(User)
        .join(MemberBlock, MemberBlock.blocker_id == User.id)
        .filter(MemberBlock.blocked_id == user.id, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    ]
    return {"blocked": blocked, "blocked_me": blocked_me}


@router.delete("/members/block/{user_id}")
def unblock_member(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user_id == user.id:
        raise HTTPException(status_code=422, detail="You cannot unblock your own account.")
    rate_limit.consume("community.block", user.id, rate_limit.BLOCK_CHANGE)
    existing = db.query(MemberBlock).filter(
        MemberBlock.blocker_id == user.id,
        MemberBlock.blocked_id == user_id,
    ).first()
    if existing is None:
        # DELETE is idempotent: the caller's intent -- "this member is not
        # blocked" -- already holds, so a double tap must not surface an error.
        return {"user_id": user_id, "status": "not_blocked"}
    db.delete(existing)
    _audit(db, user, "member.unblocked", "user", user_id)
    db.commit()
    return {"user_id": user_id, "status": "unblocked"}


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

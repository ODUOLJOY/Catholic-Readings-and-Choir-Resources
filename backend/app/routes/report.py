"""Content reporting and moderation review.

This router is the single authoritative entry point for member reports. It was
previously written but never registered, so the in-app "Report Content" button
posted to a route that did not exist and always failed. It has been hardened at
the same time:

* scope is derived server-side from the reported resource, never accepted from
  the request, so a client cannot widen who can review its report;
* review is authorized through the permission + organizational-scope model
  instead of the coarse ``user.role == "admin"`` check, so a parish moderator
  only ever sees reports from their own parish;
* a member can read back their own reports, but never another member's;
* the reporter's identity is withheld from the reported user;
* every moderation action is written to the community audit log.
"""
from typing import Literal

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.community import (
    CommunityAnnouncement,
    CommunityAuditLog,
    CommunityConversation,
    CommunityEvent,
    CommunityGroup,
    CommunityMessage,
    CommunitySuggestion,
    ConversationMember,
    PrayerIntention,
)
from app.models.report import ContentReport
from app.models.user import User
from app.routes.auth_dependency import get_current_user
from app.services import rate_limit
from app.services.authorization import (
    can_moderate_platform_content,
    can_review_moderation_report,
    moderation_scope_ids,
    user_belongs_to_scope,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

REPORTABLE_RESOURCE_TYPES = {
    "reading",
    "saint",
    "choir",
    "choir_resource",
    "message",
    "announcement",
    "suggestion",
    "group",
    "event",
    "prayer_intention",
    "user_profile",
}
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
REPORT_STATUSES = {"pending", "under_review", "action_taken", "resolved", "dismissed"}
MODERATION_ACTIONS = {
    "none",
    "content_hidden",
    "warning_issued",
    "user_suspended_for_review",
    "no_action",
}
TERMINAL_REPORT_STATUSES = {"resolved", "dismissed"}
REPORT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"under_review", "action_taken", "resolved", "dismissed"},
    "under_review": {"action_taken", "resolved", "dismissed"},
    "action_taken": {"resolved", "dismissed"},
    "resolved": set(),
    "dismissed": set(),
}


class ReportCreate(BaseModel):
    resource_type: str = Field(min_length=1, max_length=40)
    resource_id: int = Field(gt=0)
    category: str = Field(default="other", max_length=40)
    reason: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=2000)

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in REPORTABLE_RESOURCE_TYPES:
            raise ValueError("That content type cannot be reported.")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in REPORT_CATEGORIES:
            raise ValueError("Unknown report category.")
        return normalized


class ReportDecision(BaseModel):
    status: Literal[
        "pending", "under_review", "action_taken", "resolved", "dismissed"
    ]
    moderation_action: Literal[
        "none",
        "content_hidden",
        "warning_issued",
        "user_suspended_for_review",
        "no_action",
    ] = "none"
    resolution_note: str | None = Field(default=None, max_length=4000)
    assigned_to: int | None = Field(default=None, gt=0)

    @field_validator("resolution_note")
    @classmethod
    def validate_resolution_note(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("A resolution note cannot be blank.")
        return value


def _audit(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: int,
    scope_type: str | None,
    scope_id: int | None,
    reason: str | None,
) -> None:
    db.add(
        CommunityAuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
        )
    )


def _resolve_scope(db: Session, resource_type: str, resource_id: int, user: User):
    """Confirm the resource exists and derive its moderation scope.

    Returns ``(scope_type, scope_id, conversation_id)``. Platform catalogue
    content legitimately has no scope; community content always resolves to the
    parish that owns the conversation, so moderators are routed correctly.
    """
    if resource_type in {"reading", "saint", "choir", "choir_resource"}:
        # Platform catalogue rows are not scoped to an organization, so they are
        # only reviewable under a global appointment.
        return None, None, None

    if resource_type == "message":
        message = db.query(CommunityMessage).filter(
            CommunityMessage.id == resource_id,
            CommunityMessage.is_deleted.is_(False),
        ).first()
        if message is None:
            raise HTTPException(status_code=404, detail="Message not found.")
        membership = db.query(ConversationMember.id).filter(
            ConversationMember.conversation_id == message.conversation_id,
            ConversationMember.user_id == user.id,
        ).first()
        if membership is None:
            # Do not confirm existence of a conversation the caller cannot see.
            raise HTTPException(status_code=404, detail="Message not found.")
        conversation = db.query(CommunityConversation).filter(
            CommunityConversation.id == message.conversation_id
        ).first()
        conversation_id = message.conversation_id
        if conversation is None or conversation.conversation_type == "direct":
            # A private conversation belongs to no parish, so its reports are
            # reviewable only under a global appointment. This keeps them out of
            # every parish queue rather than leaking them into a sibling parish.
            return None, None, conversation_id
        return conversation.scope_type, conversation.scope_id, conversation_id
    if resource_type == "announcement":
        announcement = db.query(CommunityAnnouncement).filter(
            CommunityAnnouncement.id == resource_id
        ).first()
        if announcement is None:
            raise HTTPException(status_code=404, detail="Announcement not found.")
        if announcement.audience_type == "platform":
            return None, None, None
        if announcement.audience_id is None or not user_belongs_to_scope(
            db, user, announcement.audience_type, announcement.audience_id
        ):
            raise HTTPException(status_code=404, detail="Announcement not found.")
        return announcement.audience_type, announcement.audience_id, None

    if resource_type == "suggestion":
        suggestion = db.query(CommunitySuggestion).filter(
            CommunitySuggestion.id == resource_id
        ).first()
        if suggestion is None:
            raise HTTPException(status_code=404, detail="Suggestion not found.")
        if suggestion.submitter_id != user.id and not can_review_moderation_report(
            db, user, suggestion.scope_type, suggestion.scope_id
        ):
            raise HTTPException(status_code=404, detail="Suggestion not found.")
        return suggestion.scope_type, suggestion.scope_id, None

    if resource_type == "group":
        group = db.query(CommunityGroup).filter(
            CommunityGroup.id == resource_id,
            CommunityGroup.is_active.is_(True),
        ).first()
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found.")
        if not user_belongs_to_scope(db, user, group.scope_type, group.scope_id):
            raise HTTPException(status_code=404, detail="Group not found.")
        return group.scope_type, group.scope_id, None

    if resource_type == "event":
        event = db.query(CommunityEvent).filter(
            CommunityEvent.id == resource_id,
        ).first()
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found.")
        if event.is_published is not True and not can_review_moderation_report(
            db, user, event.scope_type, event.scope_id
        ):
            raise HTTPException(status_code=404, detail="Event not found.")
        if not user_belongs_to_scope(db, user, event.scope_type, event.scope_id):
            raise HTTPException(status_code=404, detail="Event not found.")
        return event.scope_type, event.scope_id, None

    if resource_type == "prayer_intention":
        intention = db.query(PrayerIntention).filter(
            PrayerIntention.id == resource_id,
        ).first()
        if intention is None:
            raise HTTPException(status_code=404, detail="Prayer intention not found.")
        scope = _intention_scope(intention)
        if scope is not None and not user_belongs_to_scope(db, user, *scope):
            raise HTTPException(
                status_code=404, detail="Prayer intention not found."
            )
        return (scope[0], scope[1], None) if scope else (None, None, None)

    # user_profile is the only remaining reportable type: scope the report to the
    # reported member's own parish rather than to the reporting member's, so a
    # report about another parish lands with the parish that can act on it.
    if resource_type != "user_profile":
        # ``validate_resource_type`` rejects unknown types before this point, so
        # reaching here means the two sets have drifted apart.
        raise HTTPException(status_code=422, detail="That content type cannot be reported.")
    target = db.query(User).filter(User.id == resource_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if target.parish_id is None:
        return None, None, None
    return "parish", target.parish_id, None


def _intention_scope(intention: PrayerIntention) -> tuple[str, int] | None:
    """The most specific organizational scope an intention is visible in."""
    if intention.visibility == "parish" and intention.parish_id is not None:
        return ("parish", intention.parish_id)
    if intention.visibility == "diocese" and intention.diocese_id is not None:
        return ("diocese", intention.diocese_id)
    return None


@router.post("/", status_code=201)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a report about content.

    The caller must be able to see the resource, and the moderation scope is
    derived from it. A member who reports the same resource repeatedly is
    rate-limited rather than blocked, so a genuine duplicate report from two
    people still reaches a moderator.
    """
    rate_limit.consume("reports.create", current_user.id, rate_limit.REPORT_SUBMIT)
    scope_type, scope_id, conversation_id = _resolve_scope(
        db, payload.resource_type, payload.resource_id, current_user
    )
    duplicate_id = db.query(ContentReport.id).filter(
        ContentReport.reporter_id == current_user.id,
        ContentReport.resource_type == payload.resource_type,
        ContentReport.resource_id == payload.resource_id,
        ContentReport.status.in_(["pending", "under_review"]),
    ).scalar()
    if duplicate_id is not None:
        return {
            "message": "You have already reported this content.",
            "report_id": duplicate_id,
            "status": "pending",
            "duplicate": True,
        }
    report = ContentReport(
        reporter_id=current_user.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        category=payload.category,
        reason=payload.reason,
        description=payload.description,
        scope_type=scope_type,
        scope_id=scope_id,
        conversation_id=conversation_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _audit(
        db,
        current_user,
        "report.submitted",
        "content_report",
        report.id,
        scope_type,
        scope_id,
        f"{payload.category}: {payload.reason}",
    )
    db.commit()
    return {
        "message": "Report submitted.",
        "report_id": report.id,
        "status": report.status,
        "category": report.category,
    }


def _serialize(
    db: Session,
    report: ContentReport,
    viewer: User,
    is_moderator: bool,
) -> dict:
    reporter = (
        db.query(User).filter(User.id == report.reporter_id).first()
        if report.reporter_id
        else None
    )
    payload = {
        "id": report.id,
        "resource_type": report.resource_type,
        "resource_id": report.resource_id,
        "category": report.category,
        "reason": report.reason,
        "description": report.description,
        "status": report.status,
        "scope_type": report.scope_type,
        "scope_id": report.scope_id,
        "created_at": report.created_at,
        "reviewed_at": report.reviewed_at,
        "moderation_action": report.moderation_action,
        "resolution": report.resolution,
        "is_mine": report.reporter_id == viewer.id,
    }
    # Moderators need the reporter to follow up; members only ever see their own
    # report, so the identity is only ever attached for authorized reviewers.
    if is_moderator:
        payload["reporter_id"] = report.reporter_id
        payload["reporter_name"] = reporter.full_name if reporter else None
        payload["assigned_to"] = report.assigned_to
        payload["resolution_note"] = report.resolution_note
    elif report.reporter_id == viewer.id:
        payload["resolution_note"] = report.resolution_note
    return payload


@router.get("/")
def list_reports(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reports visible to the caller.

    A super admin sees every report. A moderator sees reports inside the scopes
    they are assigned to. Anyone else sees only the reports they filed, which is
    what lets a member track whether their concern was acted on.
    """
    if status_filter is not None and status_filter not in REPORT_STATUSES:
        raise HTTPException(status_code=422, detail="Unknown report status.")

    scopes = moderation_scope_ids(db, current_user)
    query = db.query(ContentReport)
    if scopes is None:
        is_moderator = True
    elif scopes:
        is_moderator = True
        conditions = [
            (ContentReport.scope_type == scope_type)
            & (ContentReport.scope_id == scope_id)
            for scope_type, scope_id in scopes
        ]
        # Unscoped reports are deliberately excluded. They cover platform
        # catalogue content and direct messages, and
        # ``can_review_moderation_report`` only lets a globally appointed
        # moderator action those, so listing them here would disclose reports a
        # parish moderator is not permitted to review.
        query = query.filter(or_(*conditions))
    else:
        is_moderator = False

    if not is_moderator:
        query = query.filter(ContentReport.reporter_id == current_user.id)
    if status_filter is not None:
        query = query.filter(ContentReport.status == status_filter)

    total = query.count()
    reports = (
        query.order_by(ContentReport.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "reports": [_serialize(db, report, current_user, is_moderator) for report in reports],
        "total": total,
        "limit": limit,
        "offset": offset,
        "is_moderator": is_moderator,
    }


@router.patch("/{report_id}")
def decide_report(
    report_id: int,
    payload: ReportDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a report through the moderation workflow and record the action."""
    report = db.query(ContentReport).filter(
        ContentReport.id == report_id
    ).with_for_update().first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    if not can_review_moderation_report(
        db, current_user, report.scope_type, report.scope_id
    ):
        raise HTTPException(
            status_code=403, detail="You cannot moderate this report."
        )
    permitted = REPORT_STATUS_TRANSITIONS.get(report.status, set())
    if payload.status not in permitted:
        if report.status in TERMINAL_REPORT_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"This report is already {report.status}.",
            )
        raise HTTPException(
            status_code=409,
            detail=f"A {report.status} report cannot move to {payload.status}.",
        )
    if payload.status in TERMINAL_REPORT_STATUSES and not payload.resolution_note:
        raise HTTPException(
            status_code=422,
            detail="A resolution note is required to close a report.",
        )
    if (
        payload.assigned_to is not None
        and payload.assigned_to != current_user.id
        and not can_moderate_platform_content(db, current_user)
    ):
        # Delegating review is an administrative act, not a moderator one.
        raise HTTPException(
            status_code=403,
            detail="Only an administrator may reassign a report.",
        )

    if (
        payload.moderation_action == "content_hidden"
        and report.resource_type == "message"
    ):
        message = db.query(CommunityMessage).filter(
            CommunityMessage.id == report.resource_id
        ).with_for_update().first()
        if message is not None and not message.is_deleted:
            message.is_deleted = True
            _audit(
                db,
                current_user,
                "message.hidden_by_moderation",
                "message",
                message.id,
                report.scope_type,
                report.scope_id,
                payload.resolution_note or "Hidden as the outcome of a report.",
            )

    previous_status = report.status
    report.status = payload.status
    report.moderation_action = payload.moderation_action
    report.resolution_note = payload.resolution_note
    report.assigned_to = payload.assigned_to or report.assigned_to or current_user.id
    report.reviewer_id = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)
    _audit(
        db,
        current_user,
        f"report.{payload.status}",
        "content_report",
        report.id,
        report.scope_type,
        report.scope_id,
        payload.resolution_note
        or f"{previous_status} -> {payload.status} ({payload.moderation_action})",
    )
    db.commit()
    db.refresh(report)
    return {
        "id": report.id,
        "status": report.status,
        "previous_status": previous_status,
        "moderation_action": report.moderation_action,
        "assigned_to": report.assigned_to,
        "reviewed_at": report.reviewed_at,
    }


@router.get("/statistics")
def report_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Report counts across the caller's authorized moderation scope."""
    scopes = moderation_scope_ids(db, current_user)
    if scopes is None:
        query = db.query(ContentReport)
    elif scopes:
        # Mirrors ``list_reports``: counts follow the same scope filter, so a
        # scoped moderator's totals cannot exceed the rows they can open.
        conditions = [
            (ContentReport.scope_type == scope_type)
            & (ContentReport.scope_id == scope_id)
            for scope_type, scope_id in scopes
        ]
        query = db.query(ContentReport).filter(or_(*conditions))
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required.",
        )
    counts = {
        row[0]: row[1]
        for row in query.with_entities(
            ContentReport.status, func.count(ContentReport.id)
        )
        .group_by(ContentReport.status)
        .all()
    }
    return {
        "by_status": counts,
        "total": sum(counts.values()),
        "is_unrestricted": scopes is None,
    }

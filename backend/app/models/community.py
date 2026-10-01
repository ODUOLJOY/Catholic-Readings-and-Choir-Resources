from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role", "scope_type", "scope_id", "ministry",
            name="uq_role_assignment_scope",
        ),
        CheckConstraint(
            "scope_type IN ('global', 'diocese', 'deanery', 'parish', 'group')",
            name="ck_role_assignment_scope_type",
        ),
        CheckConstraint(
            "(scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type <> 'global' AND scope_id IS NOT NULL)",
            name="ck_role_assignment_scope_id",
        ),
        Index("ix_role_assignments_scope", "scope_type", "scope_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int | None] = mapped_column(Integer)
    ministry: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParishMembership(Base):
    __tablename__ = "parish_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "parish_id", name="uq_user_parish_membership"),
        CheckConstraint(
            "status IN ('pending', 'active', 'rejected', 'transferred')",
            name="ck_parish_membership_status",
        ),
        Index("ix_parish_memberships_parish_status", "parish_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    parish_id: Mapped[int] = mapped_column(ForeignKey("parishes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class RoleRequest(Base):
    __tablename__ = "role_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'more_information_required', 'approved', 'rejected')",
            name="ck_role_request_status",
        ),
        CheckConstraint(
            "scope_type IN ('diocese', 'deanery', 'parish', 'group')",
            name="ck_role_request_scope_type",
        ),
        Index("ix_role_requests_scope_status", "scope_type", "scope_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    requested_role: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ministry: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_information: Mapped[str | None] = mapped_column(Text)
    supporting_document_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="submitted", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommunityGroup(Base):
    __tablename__ = "community_groups"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('diocese', 'deanery', 'parish')",
            name="ck_community_group_scope_type",
        ),
        Index("ix_community_groups_scope", "scope_type", "scope_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("community_groups.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityAnnouncement(Base):
    __tablename__ = "community_announcements"
    __table_args__ = (
        CheckConstraint(
            "audience_type IN ('platform', 'diocese', 'parish', 'group')",
            name="ck_announcement_audience_type",
        ),
        CheckConstraint(
            "(audience_type = 'platform' AND audience_id IS NULL) OR "
            "(audience_type <> 'platform' AND audience_id IS NOT NULL)",
            name="ck_announcement_audience_id",
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'archived')",
            name="ck_announcement_status",
        ),
        Index("ix_announcements_audience_status", "audience_type", "audience_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    announcement_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    audience_type: Mapped[str] = mapped_column(String(20), nullable=False)
    audience_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attachment_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommunitySuggestion(Base):
    __tablename__ = "community_suggestions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'in_discussion', 'accepted', 'implemented', 'declined', 'archived')",
            name="ck_suggestion_status",
        ),
        Index("ix_suggestions_scope_status", "scope_type", "scope_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submitter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="submitted", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommunityEvent(Base):
    __tablename__ = "community_events"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('diocese', 'parish', 'group')",
            name="ck_community_event_scope_type",
        ),
        Index("ix_community_events_scope_start", "scope_type", "scope_id", "starts_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(255))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrayerIntention(Base):
    __tablename__ = "prayer_intentions"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('private', 'parish', 'diocese', 'public')",
            name="ck_prayer_intention_visibility",
        ),
        Index("ix_prayer_intentions_visibility", "visibility", "parish_id", "diocese_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    parish_id: Mapped[int | None] = mapped_column(ForeignKey("parishes.id"))
    diocese_id: Mapped[int | None] = mapped_column(ForeignKey("dioceses.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrayerReaction(Base):
    __tablename__ = "prayer_reactions"
    __table_args__ = (
        UniqueConstraint("intention_id", "user_id", name="uq_prayer_reaction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intention_id: Mapped[int] = mapped_column(ForeignKey("prayer_intentions.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reaction: Mapped[str] = mapped_column(String(20), nullable=False, default="praying")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityNotificationPreference(Base):
    __tablename__ = "community_notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_community_notification_preference_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    announcements: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    events: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role_requests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    messages: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommunityConversation(Base):
    __tablename__ = "community_conversations"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('parish', 'group')",
            name="ck_community_conversation_scope",
        ),
        Index("ix_community_conversations_scope", "scope_type", "scope_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("community_groups.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("community_conversations.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityMessage(Base):
    __tablename__ = "community_messages"
    __table_args__ = (
        Index("ix_community_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("community_conversations.id"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("community_messages.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(500))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageReaction(Base):
    __tablename__ = "message_reactions"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "reaction", name="uq_message_reaction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("community_messages.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reaction: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemberBlock(Base):
    __tablename__ = "member_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_member_block"),
        CheckConstraint("blocker_id <> blocked_id", name="ck_member_block_not_self"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityAuditLog(Base):
    __tablename__ = "community_audit_logs"
    __table_args__ = (
        Index("ix_community_audit_target", "target_type", "target_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer)
    role: Mapped[str | None] = mapped_column(String(50))
    scope_type: Mapped[str | None] = mapped_column(String(20))
    scope_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

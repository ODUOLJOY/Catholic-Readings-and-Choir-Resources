"""Add scoped roles and community features.

Revision ID: 20261001_01
Revises: 20261006_01
"""
from alembic import op

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

revision = "20261001_01"
# Chained onto the baseline repair rather than standing alone as a second root.
# It was `None`, which alongside the repair revisions would have left Alembic
# with multiple heads and made `upgrade head` refuse to run.
down_revision = "20261006_01"
branch_labels = None
depends_on = None

NEW_TABLES = [
    RoleAssignment.__table__,
    ParishMembership.__table__,
    RoleRequest.__table__,
    CommunityGroup.__table__,
    GroupMembership.__table__,
    CommunityAnnouncement.__table__,
    CommunitySuggestion.__table__,
    CommunityEvent.__table__,
    PrayerIntention.__table__,
    PrayerReaction.__table__,
    CommunityNotificationPreference.__table__,
    CommunityConversation.__table__,
    ConversationMember.__table__,
    CommunityMessage.__table__,
    MessageReaction.__table__,
    MemberBlock.__table__,
    CommunityAuditLog.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    offline = op.get_context().as_sql
    if not offline:
        from app.services.migration_preflight import verify_legacy_schema

        verify_legacy_schema(bind)
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=not offline)
    from sqlalchemy import exists, insert, literal, select
    from app.models.user import User

    bind.execute(
        insert(ParishMembership.__table__).from_select(
            ["user_id", "parish_id", "status"],
            select(User.id, User.parish_id, literal("pending"))
            .where(
                User.parish_id.is_not(None),
                ~exists().where(
                    ParishMembership.user_id == User.id,
                    ParishMembership.parish_id == User.parish_id,
                ),
            ),
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)

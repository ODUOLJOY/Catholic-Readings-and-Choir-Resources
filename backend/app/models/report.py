from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ContentReport(Base):
    """A member report about community or catalogue content.

    ``scope_type``/``scope_id`` are always derived server-side from the reported
    resource. They exist so moderators only ever see reports inside the
    organizational scope they are authorized for, and so a client can never
    widen its own visibility by sending a different parish id.
    """

    __tablename__ = "content_reports"
    __table_args__ = (
        # Index and foreign-key *names* are kept byte-identical to the
        # authoritative definition in migrations/versions/20261002_10 (see
        # ``_create_content_reports`` / ``_report_columns``). Matching here is
        # what makes ``Base.metadata.create_all`` -- which the migration tests
        # stamp and roll back against -- produce a schema congruent with the
        # migration. On SQLite a mismatch between an unnamed model FK / a
        # mismatched index and the named, indexed migration definition is exactly
        # the "column-drop / key mismatch while rebuilding content_reports"
        # failure the revision docstring describes, so every constraint name and
        # index here mirrors the migration rather than being left to reflection.
        Index("ix_content_reports_reporter_id", "reporter_id"),
        Index("ix_content_reports_status", "status"),
        Index("ix_content_reports_status_scope", "status", "scope_type", "scope_id"),
        Index("ix_content_reports_resource", "resource_type", "resource_id"),
    )

    id = Column(Integer, primary_key=True)
    reporter_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_content_reports_reporter_id"),
        nullable=True,
    )
    resource_type = Column(String(40), nullable=False)  # message, reading, saint, choir
    resource_id = Column(Integer, nullable=False)
    reason = Column(String(100), nullable=False)
    description = Column(Text)
    # pending, under_review, action_taken, resolved, dismissed
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_content_reports_reviewer_id"),
        nullable=True,
    )
    resolution = Column(String(100), nullable=True)
    category = Column(String(40), nullable=True)
    scope_type = Column(String(20), nullable=True)
    scope_id = Column(Integer, nullable=True)
    conversation_id = Column(Integer, nullable=True)
    assigned_to = Column(
        Integer,
        ForeignKey("users.id", name="fk_content_reports_assigned_to"),
        nullable=True,
    )
    resolution_note = Column(Text, nullable=True)
    moderation_action = Column(String(40), nullable=True)

    reporter = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="reports",
    )
    reviewer = relationship("User", foreign_keys=[reviewer_id])

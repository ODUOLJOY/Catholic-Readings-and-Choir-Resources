from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ChoirResource(Base):
    __tablename__ = "choir_resources"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Category and Language
    category = Column(String(100), nullable=False, index=True)
    language = Column(String(20), nullable=False, default="English", index=True)

    # File Info
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, audio, video, etc.
    file_size = Column(Integer, nullable=True)  # in bytes
    storage_key = Column(String(1000), nullable=True, index=True)

    # Metadata
    composer = Column(String(255), nullable=True)
    lyrics = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # in seconds for audio/video

    # Structured metadata — mirrors the frontend ChoirResource interface and the
    # choir-library product vision. Every field is nullable so the extension is
    # backwards-compatible for rows created before these columns existed.
    alternative_title = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    arranger = Column(String(255), nullable=True)
    # Vocal/part assignment, e.g. "SATB", "SSA", "Soprano", "Choir".
    voice_part = Column(String(50), nullable=True, index=True)
    # Liturgical season, e.g. Advent, Christmas, Lent, Easter, Ordinary Time.
    season = Column(String(50), nullable=True, index=True)
    # Musical key signature, e.g. "C major", "A minor".
    key_signature = Column(String(50), nullable=True, index=True)
    # Tempo marking, e.g. "Allegro", "Andante", "120 BPM".
    tempo = Column(String(50), nullable=True, index=True)

    # Status
    is_approved = Column(Boolean, default=False, index=True)
    is_published = Column(Boolean, default=False, index=True)
    moderation_status = Column(String(30), nullable=False, default="pending", index=True)
    reviewed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Upload Info
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    parish_id = Column(
        Integer,
        ForeignKey("parishes.id"),
        nullable=True,
        index=True,
    )

    uploader = relationship(
        "User",
        back_populates="choir_resources",
        foreign_keys=[uploaded_by],
    )

    # Ratings and Comments
    rating = Column(Integer, nullable=True)  # 1-5 stars
    download_count = Column(Integer, default=0)

    # Dates
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    published_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

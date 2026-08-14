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
    language = Column(String(20), nullable=False, default="English")

    # File Info
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, audio, video, etc.
    file_size = Column(Integer, nullable=True)  # in bytes

    # Metadata
    composer = Column(String(255), nullable=True)
    lyrics = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # in seconds for audio/video

    # Status
    is_approved = Column(Boolean, default=False, index=True)
    is_published = Column(Boolean, default=False, index=True)

    # Upload Info
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    uploader = relationship("User")

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

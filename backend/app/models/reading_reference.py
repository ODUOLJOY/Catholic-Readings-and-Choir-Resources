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


class ReadingReference(Base):
    """
    Structured Scripture reading reference.
    
    Stores only metadata (book, chapter, verse ranges) - NOT the actual text.
    Supports complex references like:
    - Daniel 7:9-10,13-14
    - Psalm 104(105):2-7
    - 1 Corinthians 12:12-14,27-31
    """
    __tablename__ = "reading_references"

    id = Column(Integer, primary_key=True, index=True)
    
    # Link to reading set
    reading_set_id = Column(Integer, ForeignKey("reading_sets.id"), nullable=False)
    reading_set = relationship("ReadingSet", back_populates="reading_references")
    
    # Reading type
    reading_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # FIRST_READING, RESPONSORIAL_PSALM, SECOND_READING, GOSPEL_ACCLAMATION, GOSPEL, etc.
    
    # Structured reference components
    book = Column(String(100), nullable=False, index=True)  # Galatians, Psalm, etc.
    chapter_start = Column(Integer, nullable=True)
    verse_start = Column(String(50), nullable=True)  # Supports "2-3" or "2a"
    chapter_end = Column(Integer, nullable=True)
    verse_end = Column(String(50), nullable=True)
    
    # Human-readable display reference (preserves original format)
    display_reference = Column(String(255), nullable=False)  # "Galatians 3:22-29"
    
    # Psalm variant (e.g., "104(105)" for alternative numbering)
    psalm_number_variant = Column(String(50), nullable=True)
    
    # Selection options
    sequence = Column(Integer, default=0)  # Order within reading type (for alternatives)
    is_alternative = Column(Boolean, default=False)  # Is this an alternative reading?
    is_optional = Column(Boolean, default=False)  # Is this reading optional?
    is_primary = Column(Boolean, default=True)  # Is this the default choice?
    
    # Additional metadata
    lectionary_number = Column(String(50), nullable=True)
    comment = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReadingSet(Base):
    """
    A set of reading references for a specific liturgical day and celebration.
    
    Multiple reading sets can exist for a single day:
    - weekday_default (feria readings)
    - strictly_proper (memorial/feast readings)
    - suggested (optional readings)
    - common_option (common of saints)
    - alternative
    """
    __tablename__ = "reading_sets"

    id = Column(Integer, primary_key=True, index=True)
    
    # Link to liturgical day
    liturgical_day_id = Column(Integer, ForeignKey("liturgical_days.id"), nullable=False)
    liturgical_day = relationship("LiturgicalDay", back_populates="reading_sets")
    
    # Reading set type and status
    reading_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # daily, proper, common, alternative
    selection_status = Column(
        String(50),
        nullable=False,
        default="weekday_default",
        index=True
    )  # strictly_proper, suggested, weekday_default, common_option, alternative
    
    # Celebration this set is for (if different from day's main celebration)
    celebration_id = Column(Integer, nullable=True)
    celebration_name = Column(String(255), nullable=True)
    
    # Lectionary reference
    lectionary_number = Column(String(50), nullable=True)
    
    # Source tracking
    source_id = Column(Integer, ForeignKey("liturgical_sources.id"), nullable=True)
    source = relationship("LiturgicalSource")
    
    # Authority level (for precedence decisions)
    authority_level = Column(String(50), nullable=True)  # general_roman, national, diocesan, parish
    
    # Verification
    verification_status = Column(String(50), default="unverified")  # unverified, verified, requires_review
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    reading_references = relationship("ReadingReference", back_populates="reading_set", cascade="all, delete-orphan")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

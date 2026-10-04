from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class LiturgicalDay(Base):
    __tablename__ = "liturgical_days"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Liturgical Year cycles
    liturgical_year = Column(String(5), nullable=True)  # A, B, C (legacy, for backward compatibility)
    sunday_cycle = Column(String(5), nullable=False)  # A, B, C (Sunday lectionary)
    weekday_cycle = Column(String(5), nullable=False)  # I, II (weekday lectionary)
    
    # Season and week
    season = Column(String(50), nullable=False, index=True)
    week_number = Column(Integer, nullable=True)
    
    # Celebration
    celebration_name = Column(String(255), nullable=False)
    celebration_rank = Column(String(50), nullable=False, index=True)  # Solemnity, Feast, Memorial, Feria, etc.
    liturgical_color = Column(String(20), nullable=False)
    
    # Legacy string references (deprecated - use reading_sets instead)
    first_reading_reference = Column(String(255), nullable=True)
    responsorial_psalm_reference = Column(String(255), nullable=True)
    second_reading_reference = Column(String(255), nullable=True)
    gospel_reference = Column(String(255), nullable=True)
    
    # Structured Reading Sets
    reading_sets = relationship("ReadingSet", back_populates="liturgical_day", cascade="all, delete-orphan")
    
    # Region & Source Tracking
    region = Column(String(10), default="KE", index=True)  # KE, US, Universal
    diocese_id = Column(Integer, nullable=True)  # For future diocesan proper calendars
    parish_id = Column(Integer, nullable=True)  # For future parish proper calendars
    
    source_id = Column(Integer, ForeignKey("liturgical_sources.id"), nullable=True)
    source = relationship("LiturgicalSource")
    source_record_id = Column(String(255), nullable=True)
    
    verification_status = Column(String(50), default="unverified", index=True)  # unverified, verified, requires_review
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class LiturgicalSource(Base):
    __tablename__ = "liturgical_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    country = Column(String(10), nullable=True)
    authority_level = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=10)
    last_checked = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

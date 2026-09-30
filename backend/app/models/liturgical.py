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
    liturgical_year = Column(String(5), nullable=False) # A, B, C
    season = Column(String(50), nullable=False)
    week_number = Column(Integer, nullable=True)
    celebration_name = Column(String(255), nullable=False)
    celebration_rank = Column(String(50), nullable=False) # Solemnity, Feast, etc.
    liturgical_color = Column(String(20), nullable=False)
    
    # Reading References (Legacy - Will be replaced by reading_sets)
    first_reading_reference = Column(String(255), nullable=True)
    responsorial_psalm_reference = Column(String(255), nullable=True)
    second_reading_reference = Column(String(255), nullable=True)
    gospel_reference = Column(String(255), nullable=True)
    
    # New Reading Sets
    reading_sets = relationship("ReadingSet", back_populates="liturgical_day", cascade="all, delete-orphan")
    
    # Region & Source Tracking
    region = Column(String(10), default="KE", index=True) # KE, US, Universal
    source_id = Column(Integer, ForeignKey("liturgical_sources.id"), nullable=True)
    source = relationship("LiturgicalSource")
    source_record_id = Column(String(255), nullable=True)
    verification_status = Column(String(50), default="unverified")
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ReadingSet(Base):
    __tablename__ = "reading_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    liturgical_day_id = Column(Integer, ForeignKey("liturgical_days.id"), nullable=False)
    liturgical_day = relationship("LiturgicalDay", back_populates="reading_sets")
    
    reading_type = Column(String(50), nullable=False) # daily, proper, common, alternative
    celebration_id = Column(Integer, nullable=True)
    lectionary_number = Column(String(50), nullable=True)
    
    first_reading_reference = Column(String(255), nullable=True)
    responsorial_psalm_reference = Column(String(255), nullable=True)
    second_reading_reference = Column(String(255), nullable=True)
    gospel_reference = Column(String(255), nullable=True)
    
    source_id = Column(Integer, ForeignKey("liturgical_sources.id"), nullable=True)
    source = relationship("LiturgicalSource")
    
    authority_level = Column(String(50), nullable=True)
    selection_status = Column(String(50), default="weekday_default") # strictly_proper, suggested, weekday_default, common_option, alternative
    verification_status = Column(String(50), default="unverified")
    
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

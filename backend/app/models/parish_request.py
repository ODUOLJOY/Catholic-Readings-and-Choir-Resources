from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.database import Base

class ParishRequest(Base):
    __tablename__ = "parish_requests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parish_name = Column(String(255), nullable=False)
    diocese_name = Column(String(255), nullable=True)
    deanery_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    additional_info = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # pending, reviewing, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

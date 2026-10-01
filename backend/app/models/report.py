from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class ContentReport(Base):
    __tablename__ = "content_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"))
    resource_type = Column(String)  # 'reading', 'saint', 'choir'
    resource_id = Column(Integer)
    reason = Column(String)
    description = Column(String)
    status = Column(String, default="pending")  # pending, reviewing, resolved, rejected
    created_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution = Column(String, nullable=True)

    reporter = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="reports",
    )
    reviewer = relationship("User", foreign_keys=[reviewer_id])

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base

class Diocese(Base):
    __tablename__ = "dioceses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    deaneries = relationship("Deanery", back_populates="diocese")

class Deanery(Base):
    __tablename__ = "deaneries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    diocese_id = Column(Integer, ForeignKey("dioceses.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    verification_status = Column(String(50), default="needs_review", nullable=False)
    diocese = relationship("Diocese", back_populates="deaneries")
    parishes = relationship("Parish", back_populates="deanery")

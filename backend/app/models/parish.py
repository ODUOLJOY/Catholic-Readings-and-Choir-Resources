from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class Parish(Base):
    __tablename__ = "parishes"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False, unique=True, index=True)

    diocese = Column(String(255), nullable=True)

    archdiocese = Column(String(255), nullable=True)

    country = Column(String(100), nullable=False, default="Kenya")

    county = Column(String(100), nullable=True)

    town = Column(String(150), nullable=True)

    address = Column(Text, nullable=True)

    phone = Column(String(50), nullable=True)

    email = Column(String(255), nullable=True)

    website = Column(String(255), nullable=True)

    parish_priest = Column(String(255), nullable=True)

    assistant_priest = Column(String(255), nullable=True)

    logo = Column(String(500), nullable=True)

    description = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
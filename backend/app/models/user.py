from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(255), nullable=False)

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password = Column(
        String(255),
        nullable=False,
    )

    phone_number = Column(
        String(30),
        nullable=True,
    )

    profile_picture = Column(
        String(500),
        nullable=True,
    )

    language = Column(
        String(20),
        default="English",
        nullable=False,
    )

    parish_id = Column(
        Integer,
        nullable=True,
    )

    role = Column(
        String(30),
        default="user",
        nullable=False,
    )
    # user
    # admin
    # super_admin

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    email_verification_token = Column(
        String(500),
        nullable=True,
    )

    password_reset_token = Column(
        String(500),
        nullable=True,
    )

    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
    )

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

    readings = relationship(
        "Reading",
        back_populates="uploader",
        cascade="all, delete",
    )

    choir_resources = relationship(
        "ChoirResource",
        back_populates="uploader",
        cascade="all, delete",
    )

    reports = relationship(
        "Report",
        back_populates="user",
        cascade="all, delete",
    )

    favorites = relationship(
        "Favorite",
        back_populates="user",
        cascade="all, delete",
    )

    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete",
    )
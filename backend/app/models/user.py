from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    ForeignKey,
    Enum as SQLEnum,
)
from enum import Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class UserRole(str, Enum):
    USER = "user"
    CHOIR_CONTRIBUTOR = "choir_contributor"
    PARISH_ADMINISTRATOR = "parish_administrator"
    DIOCESAN_ADMINISTRATOR = "diocesan_administrator"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    DEACTIVATED = "deactivated"


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

    profile_setup_completed = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    language = Column(
        String(20),
        default="English",
        nullable=False,
    )

    parish_id = Column(
        Integer,
        ForeignKey("parishes.id"),
        nullable=True,
    )

    # Organisation membership only. Selecting a parish during registration never
    # grants administrative privileges; those come from the separate
    # RoleAssignment / RoleRequest approval workflow.
    parish = relationship("Parish", back_populates="users")

    role = Column(
        String(30),
        default="user",
        nullable=False,
    )
    # user
    # choir_contributor
    # parish_administrator
    # diocesan_administrator
    # moderator
    # admin
    # super_admin

    status = Column(
        # values_callable stores the enum values ("active") rather than the member
        # names ("ACTIVE"). This must stay in step with the enum labels and
        # server_default created by migration 09, and with the lowercase UserRole
        # values, or PostgreSQL will reject writes outright.
        SQLEnum(
            UserStatus,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    locked_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    locked_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    suspended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    suspended_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    suspension_reason = Column(
        String(500),
        nullable=True,
    )

    deactivated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    deactivated_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
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
        foreign_keys="ChoirResource.uploaded_by",
        cascade="all, delete",
    )

    reports = relationship(
        "ContentReport",
        back_populates="reporter",
        foreign_keys="ContentReport.reporter_id",
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

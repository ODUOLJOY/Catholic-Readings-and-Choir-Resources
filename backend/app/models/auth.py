from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    String,
    DateTime,
    UniqueConstraint,
    func,
)
from app.db.database import Base


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)

    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(64), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ExternalIdentity(Base):
    """A verified identity from an external provider (e.g. Google).

    The provider subject is the permanent external key; email is stored for
    auditing only and must never be used to identify an external account.
    """

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identity_provider_subject",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    provider_subject = Column(String(255), nullable=False, index=True)
    email_at_link = Column(String(255), nullable=True)

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

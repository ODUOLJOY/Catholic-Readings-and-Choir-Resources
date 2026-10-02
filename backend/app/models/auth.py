from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, func
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

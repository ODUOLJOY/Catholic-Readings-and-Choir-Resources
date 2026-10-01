from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.database import Base

class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Generic resource tracking
    resource_type: Mapped[str] = mapped_column(String(50), index=True) # 'reading', 'saint', 'choir'
    target_resource_id: Mapped[int] = mapped_column(index=True)
    
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user = relationship("User", back_populates="favorites")

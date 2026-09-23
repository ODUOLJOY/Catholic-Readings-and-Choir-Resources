from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("readings.id"), index=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("choir_resources.id"), index=True)
    user = relationship("User", back_populates="favorites")

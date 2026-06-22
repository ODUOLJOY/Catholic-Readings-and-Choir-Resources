from sqlalchemy import Column, Integer, String
from app.database import Base

class Reading(Base):

    __tablename__ = "readings"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    first_reading = Column(
        String
    )

    psalm = Column(
        String
    )

    gospel = Column(
        String
    )
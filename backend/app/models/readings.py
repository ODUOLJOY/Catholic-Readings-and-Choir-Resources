from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)

    # Date
    reading_date = Column(Date, nullable=False, unique=True, index=True)

    # Languages
    language = Column(String(20), nullable=False, default="English")

    # Liturgy
    liturgical_year = Column(String(5), nullable=False)      # A, B, C
    liturgical_season = Column(String(50), nullable=False)   # Lent, Easter...
    liturgical_color = Column(String(20), nullable=False)    # Green, White...

    feast = Column(String(255), nullable=True)
    saint_of_day = Column(String(255), nullable=True)

    is_holy_day = Column(Boolean, default=False)

    # First Reading
    first_reading_reference = Column(String(255), nullable=False)
    first_reading = Column(Text, nullable=False)

    # Psalm
    responsorial_psalm_reference = Column(String(255), nullable=True)
    responsorial_psalm = Column(Text, nullable=True)
    responsorial_response = Column(Text, nullable=True)

    # Second Reading
    second_reading_reference = Column(String(255), nullable=True)
    second_reading = Column(Text, nullable=True)

    # Gospel Acclamation
    gospel_acclamation = Column(Text, nullable=True)

    # Gospel
    gospel_reference = Column(String(255), nullable=False)
    gospel = Column(Text, nullable=False)

    # Reflection
    reflection = Column(Text, nullable=True)

    # Optional Prayer
    prayer = Column(Text, nullable=True)

    # Source
    source = Column(String(255), nullable=True)

    # Status
    published = Column(Boolean, default=False)
    approved = Column(Boolean, default=False)

    # Admin
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    uploader = relationship("User")

    # Dates
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
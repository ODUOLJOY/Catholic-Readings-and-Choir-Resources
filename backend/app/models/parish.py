from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.locations import SourceMetadataMixin, VerificationStatus


class Parish(Base, SourceMetadataMixin):
    """A parish of a Catholic diocese in Kenya.

    ``code`` is the stable machine-readable identifier used by the importer and
    the API. Display names are unique only *within* a deanery, because many
    dioceses legitimately have several "St. Mary's Parish" entries.
    """

    __tablename__ = "parishes"
    __table_args__ = (
        UniqueConstraint("deanery_id", "name", name="uq_parishes_deanery_name"),
    )

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False, index=True)
    code = Column(String(80), unique=True, nullable=False, index=True)

    deanery_id = Column(
        Integer,
        ForeignKey("deaneries.id"),
        nullable=False,
        index=True,
    )
    # Denormalised for query performance; kept consistent with
    # ``Deanery.diocese_id`` by the hierarchy service and the importer.
    diocese_id = Column(
        Integer,
        ForeignKey("dioceses.id"),
        nullable=False,
        index=True,
    )

    country_id = Column(
        Integer,
        ForeignKey("countries.id"),
        nullable=True,
        index=True,
    )

    # Retained for backward compatibility with existing consumers. Prefer
    # ``country_id``.
    country = Column(String(100), nullable=True)

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

    verification_status = Column(
        String(50),
        default=VerificationStatus.NEEDS_REVIEW,
        nullable=False,
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

    deanery = relationship("Deanery", back_populates="parishes")
    diocese = relationship("Diocese", back_populates="parishes")
    country_record = relationship("Country")
    users = relationship("User", back_populates="parish")


__all__ = ["Parish"]
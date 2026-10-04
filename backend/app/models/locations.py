from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class VerificationStatus:
    """Allowed values for the ``verification_status`` column."""

    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    INCOMPLETE = "INCOMPLETE"

    ALL = (VERIFIED, NEEDS_REVIEW, INCOMPLETE)


class SourceMetadataMixin:
    """Provenance columns shared by every hierarchy table.

    Parish/deanery boundaries change over time, so each record records where it
    came from and how confidently it is known.
    """

    source_url = Column(String(500), nullable=True)
    source_name = Column(String(255), nullable=True)
    source_verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(
        String(50),
        default=VerificationStatus.NEEDS_REVIEW,
        nullable=False,
    )


class Country(Base, SourceMetadataMixin):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(10), nullable=False, unique=True, index=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    provinces = relationship(
        "EcclesiasticalProvince",
        back_populates="country",
        cascade="all, delete-orphan",
    )


class EcclesiasticalProvince(Base, SourceMetadataMixin):
    """A metropolitan province, e.g. the Ecclesiastical Province of Nairobi.

    A province is *not* a diocese. Its metropolitan archdiocese is the archdiocese
    named by ``metropolitan_archdiocese_id``.
    """

    __tablename__ = "ecclesiastical_provinces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    short_name = Column(String(100), nullable=True)

    country_id = Column(
        Integer,
        ForeignKey("countries.id"),
        nullable=False,
        index=True,
    )

    metropolitan_archdiocese_id = Column(
        Integer,
        ForeignKey("dioceses.id", use_alter=True),
        nullable=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    country = relationship("Country", back_populates="provinces")
    dioceses = relationship(
        "Diocese",
        back_populates="ecclesiastical_province",
        foreign_keys="Diocese.ecclesiastical_province_id",
    )
    metropolitan_archdiocese = relationship(
        "Diocese",
        foreign_keys=[metropolitan_archdiocese_id],
        post_update=True,
    )


class Diocese(Base, SourceMetadataMixin):
    __tablename__ = "dioceses"
    __table_args__ = (UniqueConstraint("name", name="uq_dioceses_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    short_name = Column(String(100), nullable=True)

    ecclesiastical_province_id = Column(
        Integer,
        ForeignKey("ecclesiastical_provinces.id"),
        nullable=True,
        index=True,
    )

    is_archdiocese = Column(Boolean, default=False, nullable=False)

    # The Military Ordinariate is a personal ordinariate of the Holy See, not a
    # territorial diocese. It is stored here for referential completeness but is
    # excluded from the province -> diocese -> deanery -> parish cascade.
    is_military_ordinariate = Column(Boolean, default=False, nullable=False)

    erected_on = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ecclesiastical_province = relationship(
        "EcclesiasticalProvince",
        back_populates="dioceses",
        foreign_keys=[ecclesiastical_province_id],
    )
    deaneries = relationship(
        "Deanery",
        back_populates="diocese",
        cascade="all, delete-orphan",
    )
    parishes = relationship("Parish", back_populates="diocese")


class Deanery(Base, SourceMetadataMixin):
    __tablename__ = "deaneries"
    __table_args__ = (UniqueConstraint("diocese_id", "name", name="uq_deaneries_diocese_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)

    diocese_id = Column(
        Integer,
        ForeignKey("dioceses.id"),
        nullable=False,
        index=True,
    )
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

    diocese = relationship("Diocese", back_populates="deaneries")
    parishes = relationship("Parish", back_populates="deanery")


__all__ = [
    "Country",
    "Deanery",
    "Diocese",
    "EcclesiasticalProvince",
    "SourceMetadataMixin",
    "VerificationStatus",
]
"""Request/response schemas for readings.

These exist because the admin reading write routes accepted an untyped
``payload: dict`` and applied it directly:

* ``create_reading`` did ``Reading(**payload)``, so any column could be set --
  including ``published``, ``approved`` and ``uploaded_by``.
* ``update_reading`` looped over the payload with
  ``if hasattr(Reading, key)``, which has the same effect for every model
  attribute, including ``id`` (excluded) and the moderation flags.

Together those let a single admin POST mark a reading as already published and
approved, bypassing the separate ``/publish`` endpoints and the moderation
workflow they exist to enforce.

Declaring explicit schemas makes the writable field set reviewable and keeps
``published``, ``approved`` and ``uploaded_by`` under the control of the dedicated
workflow endpoints rather than an arbitrary request body.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReadingBase(BaseModel):
    """Fields an administrator may supply when creating or editing a reading."""

    reading_date: date
    language: str = Field(default="English", max_length=20)
    liturgical_year: str = Field(min_length=1, max_length=5)
    liturgical_season: str = Field(min_length=1, max_length=50)
    liturgical_color: str = Field(min_length=1, max_length=20)

    feast: Optional[str] = Field(default=None, max_length=255)
    saint_of_day: Optional[str] = Field(default=None, max_length=255)
    is_holy_day: bool = False

    first_reading_reference: str = Field(max_length=255)
    first_reading: str

    responsorial_psalm_reference: Optional[str] = Field(default=None, max_length=255)
    responsorial_psalm: Optional[str] = None
    responsorial_response: Optional[str] = None

    second_reading_reference: Optional[str] = Field(default=None, max_length=255)
    second_reading: Optional[str] = None

    gospel_acclamation: Optional[str] = None
    gospel_reference: str = Field(max_length=255)
    gospel: str

    reflection: Optional[str] = None
    prayer: Optional[str] = None

    #: Provenance for the text. Required so an administrator records where the
    #: content came from; liturgical texts are copyrighted and must not be
    #: invented or pasted in without attribution.
    source: Optional[str] = Field(default=None, max_length=255)

    # Reject unknown fields rather than ignoring them. Pydantic's default is to
    # drop extras silently, so a client sending ``approved`` would get a 200 and
    # no indication the field was discarded -- exactly the confusion that made the
    # mass-assignment bug hard to see. Forbidding extras makes the rejected write
    # visible to the caller.
    model_config = ConfigDict(extra="forbid")

    @field_validator("language", "liturgical_year", "liturgical_season", "liturgical_color")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "first_reading_reference",
        "first_reading",
        "gospel_reference",
        "gospel",
        "liturgical_year",
        "liturgical_season",
        "liturgical_color",
    )
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ReadingCreate(ReadingBase):
    """Admin creation payload.

    Deliberately omits ``published``, ``approved`` and ``uploaded_by``: a new
    reading starts unpublished and unapproved, and the author is taken from the
    authenticated session rather than the request body.
    """


class ReadingUpdate(BaseModel):
    """Partial admin edit payload.

    Every field is optional so a PATCH-style edit works, but the moderation flags
    stay out for the same reason as on creation.
    """

    language: Optional[str] = Field(default=None, max_length=20)
    liturgical_year: Optional[str] = Field(default=None, max_length=5)
    liturgical_season: Optional[str] = Field(default=None, max_length=50)
    liturgical_color: Optional[str] = Field(default=None, max_length=20)

    feast: Optional[str] = Field(default=None, max_length=255)
    saint_of_day: Optional[str] = Field(default=None, max_length=255)
    is_holy_day: Optional[bool] = None

    first_reading_reference: Optional[str] = Field(default=None, max_length=255)
    first_reading: Optional[str] = None

    responsorial_psalm_reference: Optional[str] = Field(default=None, max_length=255)
    responsorial_psalm: Optional[str] = None
    responsorial_response: Optional[str] = None

    second_reading_reference: Optional[str] = Field(default=None, max_length=255)
    second_reading: Optional[str] = None

    gospel_acclamation: Optional[str] = None
    gospel_reference: Optional[str] = Field(default=None, max_length=255)
    gospel: Optional[str] = None

    reflection: Optional[str] = None
    prayer: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=255)

    # See ReadingBase: an unrecognised field is an error, not a silent no-op.
    model_config = ConfigDict(extra="forbid")


class ReadingResponse(BaseModel):
    id: int
    reading_date: date
    language: str
    liturgical_year: str
    liturgical_season: str
    liturgical_color: str
    feast: Optional[str] = None
    saint_of_day: Optional[str] = None
    is_holy_day: bool = False
    first_reading_reference: str
    first_reading: str
    responsorial_psalm_reference: Optional[str] = None
    responsorial_psalm: Optional[str] = None
    responsorial_response: Optional[str] = None
    second_reading_reference: Optional[str] = None
    second_reading: Optional[str] = None
    gospel_acclamation: Optional[str] = None
    gospel_reference: str
    gospel: str
    reflection: Optional[str] = None
    prayer: Optional[str] = None
    source: Optional[str] = None
    published: bool = False
    approved: bool = False
    uploaded_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
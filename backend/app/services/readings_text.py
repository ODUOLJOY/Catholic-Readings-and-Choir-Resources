"""Optional public-domain reading *text* loader.

This is the text counterpart to the references-only Online Sync. It is gated by
``settings.FETCH_READING_TEXT`` (default ``False``) and only ever produces
**English** text from the public-domain **Douay-Rheims Challoner** translation
(1750) via the free, no-key ``bible-api.com`` endpoint.

Design + licence notes:
* Douay-Rheims Challoner (1750) is public domain worldwide -> legally safe to
  reproduce. It is **not** the Vatican/USCCB authorized lectionary
  translation, so it is tagged ``source="Douay-Rheims (public domain, 1750)"``
  and is never labelled "official".
* No public-domain Kiswahili biblical text exists, so Kiswahili is never
  synthesised: when ``language != English`` this loader is a no-op and
  ``GET /api/readings/{date}?language=Kiswahili`` keeps its graceful 404
  (which ``readingsService`` already maps to ``englishFallback``).
* The HTTP client is injectable so the whole thing is unit-tested with no
  network. Any fetch/translate failure is non-fatal: text simply stays
  unavailable rather than being fabricated.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import requests

from app.core.config import settings
from app.models.readings import Reading

BIBLE_API = "https://bible-api.com"
TRANSLATION = "douay-rheims"  # public domain; served by bible-api.com free of charge
SOURCE_LABEL = "Douay-Rheims (public domain, 1750)"

# Map Universalis/ReadingReference reading_type -> Reading text column.
# `first_reading` and `gospel` are NOT NULL on the model, so they are required.
_REF_BY_TYPE = {
    "FIRST_READING": "first_reading",
    "RESPONSORIAL_PSALM": "responsorial_psalm",
    "RESPONSORIAL_PSALM_RESPONSE": "responsorial_response",
    "SECOND_READING": "second_reading",
    "GOSPEL_ACCLAMATION": "gospel_acclamation",
    "GOSPEL": "gospel",
}


def fetch_douay_rheims(reference: str, http=requests, timeout: float = 15.0) -> Optional[str]:
    """Fetch Douay-Rheims text for a single scripture reference.

    Returns the text (stripped) or ``None`` on any failure -- never raises.
    """
    if not reference:
        return None
    try:
        resp = http.get(
            f"{BIBLE_API}/{reference}?translation={TRANSLATION}",
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.json().get("text")
        return text.strip() if isinstance(text, str) else None
    except Exception:
        return None


def resolve_reading_refs_for_date(db, target_date: date, region: str = "KE") -> dict:
    """Return ``{reading_type: display_reference}`` for a date.

    Reads the verified references written by the Universalis sync
    (``LiturgicalDay.reading_sets``); if the day hasn't been synced, falls back
    to the calendar engine so a date can still be populated. Returns ``{}`` if
    no references are available.
    """
    from app.models.liturgical import LiturgicalDay
    from app.services.missal_engine import MissalEngine

    day = (
        db.query(LiturgicalDay)
        .filter(LiturgicalDay.date == target_date, LiturgicalDay.region == region)
        .first()
    )
    if day is None:
        return {}

    selected = MissalEngine(db)._select_reading_set(day)
    refs: dict = {}
    for ref in getattr(selected, "reading_references", []) or []:
        if ref.reading_type and ref.display_reference:
            refs[ref.reading_type] = ref.display_reference
    return refs


def load_reading_text(
    db,
    target_date: date,
    language: str = "English",
    fetcher: Optional[Callable[..., Optional[str]]] = None,
) -> Optional[Reading]:
    """Fetch + persist Douay-Rheims text for a date (English only).

    Returns the persisted ``Reading`` row, or ``None`` when text could not be
    obtained (so the Missal page keeps its "text not yet published" state rather
    than fabricating anything). Idempotent: re-running updates the existing row.
    """
    # No PD source exists for non-English; never synthesise.
    if language.lower() != "english":
        return None

    # Honour the operator opt-in. When off, leave everything as-is.
    if not settings.FETCH_READING_TEXT:
        return None

    f = fetcher or fetch_douay_rheims
    refs = resolve_reading_refs_for_date(db, target_date)
    if not refs:
        return None  # nothing verified to text-ify

    texts = {col: f(refs.get(rt)) for rt, col in _REF_BY_TYPE.items()}
    # `first_reading` and `gospel` are NOT NULL: only persist when both exist.
    if not texts.get("first_reading") or not texts.get("gospel"):
        return None

    # Season/colour come from the pure calendar engine (no DB hit) so the
    # persisted text row is always well-formed even if the day row is partial.
    from app.services.calendar import get_calendar_info

    cal = get_calendar_info(target_date)
    data = {
        "reading_date": target_date,
        "language": "English",
        "published": True,
        "approved": False,
        "source": SOURCE_LABEL,
        "liturgical_year": str(target_date.year),
        "liturgical_season": cal.get("season") or "",
        "liturgical_color": cal.get("color") or "",
        "first_reading": texts["first_reading"],
        "gospel": texts["gospel"],
        "responsorial_psalm": texts["responsorial_psalm"],
        "responsorial_response": texts["responsorial_response"],
        "second_reading": texts["second_reading"],
        "gospel_acclamation": texts["gospel_acclamation"],
        "first_reading_reference": refs.get("FIRST_READING", ""),
        "gospel_reference": refs.get("GOSPEL", ""),
        "responsorial_psalm_reference": refs.get("RESPONSORIAL_PSALM"),
        "second_reading_reference": refs.get("SECOND_READING"),
        "feast": None,
    }

    existing = (
        db.query(Reading)
        .filter(Reading.reading_date == target_date, Reading.language == "English")
        .first()
    )
    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = Reading(**data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row

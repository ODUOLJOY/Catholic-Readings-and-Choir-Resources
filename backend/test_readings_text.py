"""
Hermetic tests for the optional Douay-Rheims reading-*text* loader.

Nothing here touches the network or the real database:
  * the Universalis source is replaced by `import_verified_data` seeded from a
    canned payload (the verified references already proven by test_universalis_sync),
  * the bible-api.com fetcher is replaced by an in-memory dict,
  * the SQLite engine is in-memory.

Douay-Rheims (1750) is public domain; bible-api.com serves it free with no key.
Kiswahili has no PD biblical-text source, so it must never be synthesised.
"""
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.models.readings import Reading
from app.services.liturgical_sync import LiturgicalSyncService
from app.services.readings_text import (
    SOURCE_LABEL,
    fetch_douay_rheims,
    load_reading_text,
)
import pytest
from fastapi import HTTPException

from app.routes.readings import get_reading_by_date
from app.services.universalis_sync import _parse_universalis_data


# Raw Universalis shape (references only). Routed through the real
# `_parse_universalis_data` parser to produce the exact `import_verified_data`
# payload, so the test mirrors production wiring rather than hand-typing it.
RAW_UNIVERSALIS = {
    "celebration": {"name": "Weekday", "rank": "Feria", "color": "Green"},
    "readings": {
        "first_reading": "Joel 2:12-14",
        "psalm": "Psalm 98:1-3",
        "second_reading": "Romans 12:1-2",
        "gospel": "Matthew 11:16-19",
    },
    "sunday_cycle": "A",
    "weekday_cycle": "I",
    "season": "Lent",
    "week": 5,
    "source": "Universalis",
}

DD_TEXT = {
    "Joel 2:12-14": "Douay-Rheims first reading text.",
    "Psalm 98:1-3": "Douay-Rheims responsorial psalm.",
    "Romans 12:1-2": "Douay-Rheims second reading.",
    "Matthew 11:16-19": "Douay-Rheims gospel.",
}


def _engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _seed(db):
    payload = _parse_universalis_data(RAW_UNIVERSALIS, date(2026, 3, 25), "KE")
    LiturgicalSyncService.import_verified_data(db, payload)
    db.commit()
    return db


def _fake_fetcher():
    return lambda ref: None if not ref else DD_TEXT.get(ref)


def _reading(db, d=date(2026, 3, 25)):
    return (
        db.query(Reading)
        .filter(Reading.reading_date == d, Reading.language == "English")
        .first()
    )


def test_fetch_douay_rheims_handles_http_error():
    class Boom:
        def get(self, url, timeout=15.0):
            raise ConnectionError("simulated outage")
        def raise_for_status(self):
            pass

    assert fetch_douay_rheims("Matthew 1:1", http=Boom()) is None
    assert fetch_douay_rheims("", http=Boom()) is None


def test_load_is_gated_by_flag(monkeypatch):
    db = _engine()
    try:
        _seed(db)
        monkeypatch.setattr(settings, "FETCH_READING_TEXT", False)
        assert load_reading_text(db, date(2026, 3, 25), fetcher=_fake_fetcher()) is None
        assert _reading(db) is None
    finally:
        db.close()


def test_load_is_english_only(monkeypatch):
    db = _engine()
    try:
        _seed(db)
        monkeypatch.setattr(settings, "FETCH_READING_TEXT", True)
        # Kiswahili has no PD text source -> no row, no synthesised text.
        assert load_reading_text(db, date(2026, 3, 25), language="Kiswahili",
                                fetcher=_fake_fetcher()) is None
        assert _reading(db) is None
    finally:
        db.close()


def test_load_fails_open_when_fetcher_returns_none(monkeypatch):
    db = _engine()
    try:
        _seed(db)
        monkeypatch.setattr(settings, "FETCH_READING_TEXT", True)
        assert load_reading_text(db, date(2026, 3, 25), fetcher=lambda ref: None) is None
        assert _reading(db) is None  # never fabricate a partial row
    finally:
        db.close()


def test_load_persists_douay_rheims_text(monkeypatch):
    db = _engine()
    try:
        _seed(db)
        monkeypatch.setattr(settings, "FETCH_READING_TEXT", True)

        row = load_reading_text(db, date(2026, 3, 25), fetcher=_fake_fetcher())
        assert row is not None
        assert row.published is True
        assert row.approved is False
        assert row.source == SOURCE_LABEL
        assert row.language == "English"
        assert row.first_reading == DD_TEXT["Joel 2:12-14"]
        assert row.gospel == DD_TEXT["Matthew 11:16-19"]
        assert row.responsorial_psalm == DD_TEXT["Psalm 98:1-3"]
        assert row.second_reading == DD_TEXT["Romans 12:1-2"]
        assert row.first_reading_reference == "Joel 2:12-14"
        assert row.gospel_reference == "Matthew 11:16-19"

        # The readings route resolves it -> 200 (not 404) for English.
        served = get_reading_by_date(date(2026, 3, 25), "English", db)
        assert served is not None
        assert served.first_reading == DD_TEXT["Joel 2:12-14"]
        # Kiswahili is never synthesised -> the same route 404s for Swahili.
        with pytest.raises(HTTPException) as exc:
            get_reading_by_date(date(2026, 3, 25), "Kiswahili", db)
        assert exc.value.status_code == 404

        # Idempotent: re-run updates the same row, does not duplicate.
        again = load_reading_text(db, date(2026, 3, 25), fetcher=_fake_fetcher())
        assert again.id == row.id
        assert db.query(Reading).filter(Reading.reading_date == date(2026, 3, 25)).count() == 1
    finally:
        db.close()

"""
Hermetic tests for the online lectionary sync path.

These tests do NOT touch the network and do NOT touch the real database file.
They inject a canned "fetcher" into ``MissalEngine.sync_official_lectionary``
and assert:

  * the Universalis/JSONP shape is mapped into the import payload,
  * an unreachable source returns ``success: False`` (graceful, no raise),
  * a successful sync persists a *verified* ``LiturgicalDay`` with reading
    references -- i.e. the full chain from online source -> import pipeline.
"""
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.liturgical import LiturgicalDay
from app.models.reading_reference import ReadingReference, ReadingSet
from app.routes.liturgy import get_liturgy_by_date
from app.services.missal_engine import MissalEngine
from app.services.universalis_sync import build_payload


# A minimal but representative Universalis payload (references only).
CANONICAL = {
    "celebration": {"name": "Annunciation of the Lord", "rank": "Solemnity", "color": "Purple"},
    "readings": {
        "first_reading": "Zechariah 8:18-23",
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


def _engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_build_payload_shape_from_canned_data():
    payload = build_payload(date(2026, 3, 25), "KE", fetcher=lambda d, region="KE": CANONICAL)
    assert payload is not None
    assert payload["celebration"] == "Annunciation of the Lord"
    assert payload["rank"] == "Solemnity"
    assert payload["liturgical_color"] == "Purple"
    assert payload["sunday_cycle"] == "A"
    assert payload["weekday_cycle"] == "I"
    assert payload["season"] == "Lent"
    assert payload["source"] == "Universalis"

    primary = payload["reading_sets"][0]
    assert primary["selection_status"] == "weekday_default"
    types = {r["type"] for r in primary["readings"]}
    assert {"FIRST_READING", "RESPONSORIAL_PSALM", "SECOND_READING", "GOSPEL"} <= types
    # references are populated, not fabricated text
    for ref in primary["readings"]:
        assert ref["book"]  # parse_reference populated a book code
        assert ref["display_reference"]


def test_build_payload_returns_none_when_source_unreachable():
    payload = build_payload(date(2026, 3, 25), "KE", fetcher=lambda d, region="KE": None)
    assert payload is None


def test_build_payload_tolerates_a_raising_fetcher():
    def boom(d, region="KE"):
        raise ConnectionError("simulated offline")

    assert build_payload(date(2026, 3, 25), "KE", fetcher=boom) is None


def test_sync_official_lectionary_persists_verified_day():
    db = _engine()
    try:
        result = MissalEngine.sync_official_lectionary(
            db,
            region="KE",
            target=date(2026, 3, 25),
            fetcher=lambda d, region="KE": CANONICAL,
        )

        # --- result contract -------------------------------------------------
        assert result["success"] is True
        assert result["source"] == "universalis"
        assert result["date"] == "2026-03-25"

        # --- persistence contract --------------------------------------------
        day = (
            db.query(LiturgicalDay)
            .filter(LiturgicalDay.date == date(2026, 3, 25))
            .first()
        )
        assert day is not None
        assert day.verification_status == "verified"
        assert day.celebration_name == "Annunciation of the Lord"
        assert day.celebration_rank == "Solemnity"
        assert day.liturgical_color == "Purple"
        assert day.sunday_cycle == "A"
        assert day.region == "KE"
        assert day.source is not None
        assert day.source.name == "Universalis"

        # Reading SETS + reading REFERENCES (not text) are stored.
        assert len(day.reading_sets) >= 1
        rs = day.reading_sets[0]
        assert rs.verification_status == "verified"
        assert rs.reading_references  # non-empty
        books = {ref.book for ref in rs.reading_references}
        assert "Matthew" in books or "Mt" in books

        # Idempotent: a second sync for the same date returns the same day id.
        result2 = MissalEngine.sync_official_lectionary(
            db, region="KE", target=date(2026, 3, 25),
            fetcher=lambda d, region="KE": CANONICAL,
        )
        assert result2["success"] is True
        assert result2["liturgical_day_id"] == day.id
    finally:
        db.close()


def test_sync_official_lectionary_reports_failure_when_unreachable():
    db = _engine()
    try:
        result = MissalEngine.sync_official_lectionary(
            db,
            region="KE",
            target=date(2026, 3, 25),
            fetcher=lambda d, region="KE": None,
        )
        assert result["success"] is False
        # No rows fabricated in the DB for the failed day's reading set.
        assert db.query(ReadingReference).count() == 0
    finally:
        db.close()


def test_liturgy_endpoint_returns_verified_after_sync():
    """End-to-end: after a synthetic sync, the liturgy route handler returns a
    verified day with populated reading *references* (not text)."""
    db = _engine()
    try:
        # Seed the day through the online-sync path (mocked source).
        MissalEngine.sync_official_lectionary(
            db,
            region="KE",
            target=date(2026, 3, 25),
            fetcher=lambda d, region="KE": CANONICAL,
        )
        db.commit()

        response = get_liturgy_by_date(date(2026, 3, 25), "KE", db)

        assert response["verification_status"] == "verified"
        assert response["celebration"]["name"] == "Annunciation of the Lord"
        assert response["celebration"]["rank"] == "Solemnity"
        # Reading references now populate the Missal page's Word section
        # (linked to the existing reading-detail screen -- no text duplicated).
        assert len(response["readings"]) > 0
        assert response["available_reading_sets"]
    finally:
        db.close()

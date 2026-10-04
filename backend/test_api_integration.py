"""Liturgical import and calendar engine integration tests.

Previously a single ``test_api_integration`` function wrapped every check in
``try``/``except`` and returned ``True``/``False``. pytest reports a returning
test as passing with a ``PytestReturnNotNoneWarning``, so an import failure was
recorded as a success. The checks are now independent test functions with real
assertions.

The database also moves from ``sqlite:///./test_liturgical.db`` in the working
directory to ``tmp_path``, so parallel or repeated runs cannot collide on a
shared file or leave one behind.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.liturgical import LiturgicalDay, LiturgicalSource
from app.models.reading_reference import ReadingReference, ReadingSet
from app.services.calendar import get_calendar_info
from app.services.liturgical_sync import LiturgicalSyncService

TEST_DATE = date(2026, 10, 10)
UNVERIFIED_DATE = date(2026, 9, 28)

# The calendar engine is the authority for liturgical weeks: 2026-10-10 falls in
# week 29. The previous version of this file hard-coded week 27 and never noticed,
# because its only week assertion compared the stored value against a mutation of
# the same payload rather than against the engine.
EXPECTED_WEEK = 29


def _import_payload(test_date=TEST_DATE, week=EXPECTED_WEEK):
    return {
        "date": test_date.isoformat(),
        "region": "KE",
        "celebration": "Saint Daniel Comboni, Bishop",
        "rank": "Memorial",
        "liturgical_color": "White",
        "sunday_cycle": "A",
        "weekday_cycle": "II",
        "season": "Ordinary Time",
        "week": week,
        "source": "Universalis",
        "source_record_id": f"KE_{test_date.isoformat()}",
        "reading_sets": [
            {
                "type": "daily",
                "selection_status": "weekday_default",
                "readings": [
                    {
                        "type": "FIRST_READING",
                        "book": "Galatians",
                        "display_reference": "Galatians 3:22-29",
                        "is_primary": True,
                        "is_alternative": False,
                        "is_optional": False,
                        "sequence": 0,
                    },
                    {
                        "type": "RESPONSORIAL_PSALM",
                        "book": "Psalm",
                        "display_reference": "Psalm 104(105):2-7",
                        "is_primary": True,
                        "is_alternative": False,
                        "is_optional": False,
                        "sequence": 0,
                    },
                    {
                        "type": "GOSPEL",
                        "book": "Luke",
                        "display_reference": "Luke 11:27-28",
                        "is_primary": True,
                        "is_alternative": False,
                        "is_optional": False,
                        "sequence": 0,
                    },
                ],
            },
        ],
    }


@pytest.fixture()
def db(tmp_path):
    """A disposable SQLite session holding only the liturgical tables."""
    engine = create_engine(f"sqlite:///{tmp_path / 'liturgical.db'}")

    for model in (LiturgicalSource, LiturgicalDay, ReadingSet, ReadingReference):
        model.metadata.create_all(bind=engine)

    session = sessionmaker(bind=engine)()
    session.add(
        LiturgicalSource(
            name="Universalis",
            source_type="external_api",
            country="KE",
            authority_level="primary_reference",
        )
    )
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def imported_day(db):
    """A verified liturgical day imported from the Universalis payload."""
    return LiturgicalSyncService.import_verified_data(db, _import_payload())


def test_source_is_created(db):
    source = db.query(LiturgicalSource).filter(
        LiturgicalSource.name == "Universalis"
    ).one()
    assert source.source_type == "external_api"
    assert source.country == "KE"


def test_import_returns_a_liturgical_day(db, imported_day):
    assert isinstance(imported_day, LiturgicalDay)
    assert imported_day.date == TEST_DATE
    assert imported_day.region == "KE"


def test_import_populates_the_calendar_fields(db, imported_day):
    assert imported_day.celebration_name == "Saint Daniel Comboni, Bishop"
    assert imported_day.celebration_rank == "Memorial"
    assert imported_day.liturgical_color == "White"
    assert imported_day.sunday_cycle == "A"
    assert imported_day.weekday_cycle == "II"
    assert imported_day.week_number == EXPECTED_WEEK


def test_import_marks_the_day_verified(db, imported_day):
    assert imported_day.verification_status == "verified"


def test_import_creates_one_reading_set(db, imported_day):
    assert len(imported_day.reading_sets) == 1
    reading_set = imported_day.reading_sets[0]
    assert reading_set.selection_status == "weekday_default"


def test_import_creates_all_three_reading_references(db, imported_day):
    reading_set = imported_day.reading_sets[0]
    assert len(reading_set.reading_references) == 3

    refs_by_type = {ref.reading_type: ref for ref in reading_set.reading_references}
    assert set(refs_by_type) == {
        "FIRST_READING",
        "RESPONSORIAL_PSALM",
        "GOSPEL",
    }
    assert refs_by_type["FIRST_READING"].display_reference == "Galatians 3:22-29"
    assert refs_by_type["GOSPEL"].book == "Luke"


def test_imported_day_can_be_queried_back(db, imported_day):
    queried = db.query(LiturgicalDay).filter(
        LiturgicalDay.date == TEST_DATE,
        LiturgicalDay.region == "KE",
    ).one()

    assert queried.id == imported_day.id
    assert queried.celebration_name == "Saint Daniel Comboni, Bishop"


def test_reimport_updates_instead_of_duplicating(db, imported_day):
    """The same payload must upsert, never create a second row."""
    payload = _import_payload(week=EXPECTED_WEEK + 1)
    LiturgicalSyncService.import_verified_data(db, payload)
    db.refresh(imported_day)

    assert imported_day.week_number == EXPECTED_WEEK + 1
    assert (
        db.query(LiturgicalDay)
        .filter(LiturgicalDay.date == TEST_DATE, LiturgicalDay.region == "KE")
        .count()
        == 1
    )


def test_reimport_does_not_duplicate_reading_references(db, imported_day):
    payload = _import_payload(week=EXPECTED_WEEK + 2)
    LiturgicalSyncService.import_verified_data(db, payload)
    db.refresh(imported_day)

    assert imported_day.week_number == EXPECTED_WEEK + 2
    assert len(imported_day.reading_sets) == 1
    assert len(imported_day.reading_sets[0].reading_references) == 3


def test_import_of_a_different_date_creates_a_second_day(db, imported_day):
    other = LiturgicalSyncService.import_verified_data(
        db, _import_payload(test_date=date(2026, 10, 11))
    )

    assert other.id != imported_day.id
    assert db.query(LiturgicalDay).count() == 2


def test_calendar_engine_falls_back_for_unverified_dates(db):
    """With no verified data for the date, the calendar engine takes over."""
    calendar_info = get_calendar_info(UNVERIFIED_DATE, "KE")

    assert calendar_info["date"] == UNVERIFIED_DATE.isoformat()
    assert calendar_info["season"] == "Ordinary Time"
    assert calendar_info["celebration"] == "Weekday"


def test_calendar_engine_agrees_with_the_imported_day(db, imported_day):
    """Both paths must describe the same day consistently."""
    calendar_info = get_calendar_info(TEST_DATE, "KE")

    assert calendar_info["season"] == imported_day.season
    assert calendar_info["sunday_cycle"] == imported_day.sunday_cycle
    assert calendar_info["week"] == imported_day.week_number

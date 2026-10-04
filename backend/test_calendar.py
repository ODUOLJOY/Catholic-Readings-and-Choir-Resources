from datetime import date
from types import SimpleNamespace

from app.services.calendar import (
    get_calendar_info,
    get_liturgical_season,
    get_liturgical_year,
    get_liturgical_year_sunday,
    get_liturgical_year_weekday,
)
from app.services.missal_engine import MissalEngine


def test_liturgical_cycle_changes_at_advent_and_covers_a_b_c():
    assert get_liturgical_year(date(2024, 3, 1)) == "B"
    assert get_liturgical_year(date(2025, 3, 1)) == "C"
    assert get_liturgical_year(date(2026, 9, 30)) == "A"
    assert get_liturgical_year(date(2026, 11, 28)) == "A"
    assert get_liturgical_year(date(2026, 11, 29)) == "B"


def test_sunday_cycle_matches_the_backwards_compatible_alias():
    """The retained alias must stay in step with the Sunday cycle."""
    for day in (
        date(2024, 3, 1),
        date(2025, 3, 1),
        date(2026, 9, 30),
        date(2026, 11, 28),
        date(2026, 11, 29),
        date(2027, 4, 5),
    ):
        assert get_liturgical_year(day) == get_liturgical_year_sunday(day), day


def test_weekday_cycle_alternates_i_and_ii_and_turns_at_advent():
    # Odd years are Cycle I, even years Cycle II.
    assert get_liturgical_year_weekday(date(2025, 3, 1)) == "I"
    assert get_liturgical_year_weekday(date(2026, 3, 1)) == "II"

    # The same Advent boundary that moves the Sunday cycle moves this one.
    assert get_liturgical_year_weekday(date(2026, 11, 28)) == "II"
    assert get_liturgical_year_weekday(date(2026, 11, 29)) == "I"


def test_sunday_and_weekday_cycles_are_independent():
    """The two cycles must not be conflated, which is why both are reported."""
    # 2026 is Sunday cycle A but weekday cycle II.
    assert get_liturgical_year_sunday(date(2026, 9, 30)) == "A"
    assert get_liturgical_year_weekday(date(2026, 9, 30)) == "II"
    # 2027 is Sunday cycle B but weekday cycle I.
    assert get_liturgical_year_sunday(date(2027, 3, 1)) == "B"
    assert get_liturgical_year_weekday(date(2027, 3, 1)) == "I"


def test_2026_september_30_is_the_memorial_of_saint_jerome():
    info = get_calendar_info(date(2026, 9, 30))

    assert info == {
        "date": "2026-09-30",
        "sunday_cycle": "A",
        "weekday_cycle": "II",
        "season": "Ordinary Time",
        "week": info["week"],
        "color": "White",
        "celebration": "Saint Jerome, Priest and Doctor of the Church",
        "rank": "Memorial",
        "region": "KE",
    }


def test_calendar_info_reports_both_cycles():
    info = get_calendar_info(date(2026, 11, 29))
    assert info["sunday_cycle"] == get_liturgical_year_sunday(date(2026, 11, 29))
    assert info["weekday_cycle"] == get_liturgical_year_weekday(date(2026, 11, 29))
    assert info["region"] == "KE"


def test_liturgical_seasons_include_lent_holy_week_triduum_and_easter():
    assert get_liturgical_season(date(2026, 2, 18)) == "Lent"
    assert get_liturgical_season(date(2026, 3, 30)) == "Holy Week"
    assert get_liturgical_season(date(2026, 4, 2)) == "Triduum"
    assert get_liturgical_season(date(2026, 4, 5)) == "Easter"
    assert get_liturgical_season(date(2026, 5, 24)) == "Easter"


def test_reading_selection_respects_celebration_rank_and_weekday_readings():
    weekday = SimpleNamespace(selection_status="weekday_default", id=1)
    proper = SimpleNamespace(selection_status="proper", id=2)
    strictly_proper = SimpleNamespace(selection_status="strictly_proper", id=3)
    common = SimpleNamespace(selection_status="common_option", id=4)

    def choose(rank: str, *sets):
        day = SimpleNamespace(celebration_rank=rank, reading_sets=list(sets))
        return MissalEngine(None)._select_reading_set(day)

    assert choose("Solemnity", weekday, proper) is proper
    assert choose("Feast", weekday) is weekday
    assert choose("Memorial", weekday, proper, common) is weekday
    assert choose("Obligatory Memorial", weekday, strictly_proper) is strictly_proper
    assert choose("Optional Memorial", weekday, common) is weekday
    assert choose("Weekday", weekday, proper) is weekday

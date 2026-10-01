from datetime import date
from types import SimpleNamespace

from app.services.calendar import (
    get_calendar_info,
    get_liturgical_season,
    get_liturgical_year,
)
from app.services.missal_engine import MissalEngine


def test_liturgical_cycle_changes_at_advent_and_covers_a_b_c():
    assert get_liturgical_year(date(2024, 3, 1)) == "B"
    assert get_liturgical_year(date(2025, 3, 1)) == "C"
    assert get_liturgical_year(date(2026, 9, 30)) == "A"
    assert get_liturgical_year(date(2026, 11, 28)) == "A"
    assert get_liturgical_year(date(2026, 11, 29)) == "B"


def test_2026_september_30_is_the_memorial_of_saint_jerome():
    info = get_calendar_info(date(2026, 9, 30))

    assert info == {
        "date": "2026-09-30",
        "liturgical_year": "A",
        "season": "Ordinary Time",
        "color": "White",
        "celebration": "Saint Jerome, Priest and Doctor of the Church",
        "rank": "Memorial",
    }


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

from datetime import date

from app.services.calendar import (
    get_calendar_info,
    get_liturgical_year_sunday,
    get_liturgical_year_weekday,
    get_liturgical_season,
    get_liturgical_week,
    get_liturgical_color,
    kenya_today,
)


class CalendarEngine:
    """
    Catholic Liturgical Calendar Engine.

    Responsible for determining:
    - Liturgical Season
    - Liturgical Colour
    - Liturgical Year (A/B/C for Sundays, I/II for weekdays)
    - Liturgical Week
    - Feast Information
    - Celebration Rank
    - Regional Calendar Support

    The implementation is designed so that future
    integration with official Catholic liturgical
    calendars can be added without changing the API.
    """

    @staticmethod
    def today(region: str = "KE"):
        return CalendarEngine.by_date(kenya_today(), region)

    @staticmethod
    def by_date(day: date, region: str = "KE"):
        info = get_calendar_info(day, region)

        return {
            "date": day.isoformat(),
            "sunday_cycle": get_liturgical_year_sunday(day),
            "weekday_cycle": get_liturgical_year_weekday(day),
            "liturgical_season": get_liturgical_season(day),
            "liturgical_week": get_liturgical_week(day),
            "liturgical_color": get_liturgical_color(day),
            "celebration": info.get("celebration"),
            "rank": info.get("rank"),
            "region": region,
        }

    @staticmethod
    def season(day: date):
        return get_liturgical_season(day)

    @staticmethod
    def color(day: date):
        return get_liturgical_color(day)

    @staticmethod
    def sunday_cycle(day: date):
        return get_liturgical_year_sunday(day)

    @staticmethod
    def weekday_cycle(day: date):
        return get_liturgical_year_weekday(day)

    @staticmethod
    def week(day: date):
        return get_liturgical_week(day)

    @staticmethod
    def celebration(day: date, region: str = "KE"):
        info = get_calendar_info(day, region)
        return {
            "name": info.get("celebration"),
            "rank": info.get("rank"),
            "color": info.get("color"),
        }

    @staticmethod
    def is_holy_day(day: date, region: str = "KE"):
        celebration = CalendarEngine.celebration(day, region)
        return celebration.get("rank") in ["Solemnity", "Feast"]
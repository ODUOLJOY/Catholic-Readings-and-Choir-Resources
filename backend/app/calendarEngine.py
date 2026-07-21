from datetime import date

from app.services.calendar import (
    get_calendar_info,
    get_liturgical_year,
    get_liturgical_season,
    get_liturgical_color,
)


class CalendarEngine:
    """
    Catholic Liturgical Calendar Engine.

    Responsible for determining:
    - Liturgical Season
    - Liturgical Colour
    - Liturgical Year (A/B/C)
    - Feast Information
    - Saint of the Day

    The implementation is designed so that future
    integration with official Catholic liturgical
    calendars can be added without changing the API.
    """

    @staticmethod
    def today():
        return CalendarEngine.by_date(date.today())

    @staticmethod
    def by_date(day: date):

        info = get_calendar_info(day)

        return {
            "date": day.isoformat(),
            "liturgical_year": get_liturgical_year(day),
            "liturgical_season": get_liturgical_season(day),
            "liturgical_color": get_liturgical_color(day),
            "calendar": info,
        }

    @staticmethod
    def season(day: date):
        return get_liturgical_season(day)

    @staticmethod
    def color(day: date):
        return get_liturgical_color(day)

    @staticmethod
    def year(day: date):
        return get_liturgical_year(day)

    @staticmethod
    def feast(day: date):
        info = get_calendar_info(day)
        return info.get("feast")

    @staticmethod
    def saint(day: date):
        info = get_calendar_info(day)
        return info.get("saint")

    @staticmethod
    def is_holy_day(day: date):
        info = get_calendar_info(day)
        return info.get("holy_day", False)

    @staticmethod
    def liturgical_day(day: date):
        info = get_calendar_info(day)
        return {
            "date": day.isoformat(),
            "season": info.get("season"),
            "color": info.get("color"),
            "year": info.get("year"),
            "feast": info.get("feast"),
            "saint": info.get("saint"),
            "holy_day": info.get("holy_day"),
        }
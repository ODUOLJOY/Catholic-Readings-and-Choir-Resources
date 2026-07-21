from datetime import date, timedelta


LITURGICAL_COLORS = {
    "Advent": "Purple",
    "Christmas": "White",
    "Lent": "Purple",
    "Holy Week": "Red",
    "Easter": "White",
    "Ordinary Time": "Green",
    "Pentecost": "Red",
}


def get_liturgical_year(target_date: date) -> str:
    """
    Returns Liturgical Year A, B or C.
    """

    cycle = (target_date.year - 2022) % 3

    if cycle == 0:
        return "A"

    if cycle == 1:
        return "B"

    return "C"


def easter_sunday(year: int) -> date:
    """
    Gregorian Easter calculation.
    """

    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451

    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1

    return date(year, month, day)


def get_liturgical_season(target_date: date) -> str:
    easter = easter_sunday(target_date.year)

    ash_wednesday = easter - timedelta(days=46)
    palm_sunday = easter - timedelta(days=7)
    pentecost = easter + timedelta(days=49)

    christmas = date(target_date.year, 12, 25)

    advent_start = christmas - timedelta(
        days=(christmas.weekday() + 22)
    )

    if ash_wednesday <= target_date < palm_sunday:
        return "Lent"

    if palm_sunday <= target_date < easter:
        return "Holy Week"

    if easter <= target_date <= pentecost:
        return "Easter"

    if target_date == pentecost:
        return "Pentecost"

    if advent_start <= target_date < christmas:
        return "Advent"

    if (
        target_date.month == 12
        and target_date.day >= 25
    ) or (
        target_date.month == 1
        and target_date.day <= 12
    ):
        return "Christmas"

    return "Ordinary Time"


def get_liturgical_color(target_date: date) -> str:
    season = get_liturgical_season(target_date)
    return LITURGICAL_COLORS.get(season, "Green")


def get_calendar_info(target_date: date):
    season = get_liturgical_season(target_date)

    return {
        "date": target_date.isoformat(),
        "liturgical_year": get_liturgical_year(target_date),
        "season": season,
        "color": get_liturgical_color(target_date),
    }
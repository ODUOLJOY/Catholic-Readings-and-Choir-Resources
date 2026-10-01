from datetime import date, timedelta


LITURGICAL_COLORS = {
    "Advent": "Purple",
    "Christmas": "White",
    "Lent": "Purple",
    "Holy Week": "Red",
    "Triduum": "Red",
    "Easter": "White",
    "Ordinary Time": "Green",
}


def get_advent_start(year: int) -> date:
    """Return the Sunday closest to November 30."""
    reference = date(year, 11, 30)
    days_to_sunday = (6 - reference.weekday()) % 7
    if days_to_sunday > 3:
        days_to_sunday -= 7
    return reference + timedelta(days=days_to_sunday)


def get_liturgical_year(target_date: date) -> str:
    """Return the Sunday lectionary cycle in effect on a Gregorian date."""
    year_of_cycle = target_date.year + (target_date >= get_advent_start(target_date.year))
    return ("A", "B", "C")[(year_of_cycle - 2026) % 3]


def easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
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


def _baptism_of_the_lord(year: int) -> date:
    epiphany = date(year, 1, 6)
    if epiphany.weekday() == 6:
        return epiphany + timedelta(days=1)
    return epiphany + timedelta(days=(6 - epiphany.weekday()) % 7 or 7)


def get_liturgical_season(target_date: date) -> str:
    easter = easter_sunday(target_date.year)
    ash_wednesday = easter - timedelta(days=46)
    palm_sunday = easter - timedelta(days=7)
    holy_thursday = easter - timedelta(days=3)
    pentecost = easter + timedelta(days=49)

    if easter <= target_date <= pentecost:
        return "Easter"
    if holy_thursday <= target_date < easter:
        return "Triduum"
    if palm_sunday <= target_date < holy_thursday:
        return "Holy Week"
    if ash_wednesday <= target_date < palm_sunday:
        return "Lent"

    advent_start = get_advent_start(target_date.year)
    if target_date >= advent_start and target_date < date(target_date.year, 12, 25):
        return "Advent"
    if target_date >= date(target_date.year, 12, 25):
        return "Christmas"
    if target_date <= _baptism_of_the_lord(target_date.year):
        return "Christmas"

    previous_advent = get_advent_start(target_date.year - 1)
    christmas_end = _baptism_of_the_lord(target_date.year)
    if previous_advent <= target_date <= christmas_end:
        return "Christmas"
    return "Ordinary Time"


def get_liturgical_color(target_date: date) -> str:
    easter = easter_sunday(target_date.year)
    if target_date == easter - timedelta(days=3):
        return "White"
    if target_date == easter - timedelta(days=2):
        return "Red"
    if target_date == easter - timedelta(days=1):
        return "Purple"
    season = get_liturgical_season(target_date)
    if season == "Holy Week" and target_date.weekday() == 6:
        return "Red"
    if season == "Easter" and target_date == easter + timedelta(days=49):
        return "Red"
    return LITURGICAL_COLORS.get(season, "Green")


CELEBRATIONS = {
    (1, 1): {"name": "Solemnity of Mary, Mother of God", "rank": "Solemnity", "color": "White"},
    (1, 6): {"name": "Epiphany of the Lord", "rank": "Solemnity", "color": "White"},
    (3, 19): {"name": "Saint Joseph, Spouse of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (8, 15): {"name": "Assumption of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (9, 30): {"name": "Saint Jerome, Priest and Doctor of the Church", "rank": "Memorial", "color": "White"},
    (11, 1): {"name": "All Saints", "rank": "Solemnity", "color": "White"},
    (12, 8): {"name": "Immaculate Conception of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (12, 25): {"name": "Nativity of the Lord", "rank": "Solemnity", "color": "White"},
}


def get_celebration(target_date: date) -> dict[str, str] | None:
    fixed = CELEBRATIONS.get((target_date.month, target_date.day))
    if fixed:
        return fixed

    easter = easter_sunday(target_date.year)
    relative = {
        easter - timedelta(days=46): {"name": "Ash Wednesday", "rank": "Feria", "color": "Purple"},
        easter - timedelta(days=7): {"name": "Palm Sunday of the Passion of the Lord", "rank": "Sunday", "color": "Red"},
        easter: {"name": "Easter Sunday", "rank": "Solemnity", "color": "White"},
        easter + timedelta(days=49): {"name": "Pentecost Sunday", "rank": "Solemnity", "color": "Red"},
    }
    if target_date in relative:
        return relative[target_date]
    return None


def get_calendar_info(target_date: date) -> dict[str, str]:
    celebration = get_celebration(target_date)
    if celebration is None and target_date.weekday() == 6:
        celebration = {
            "name": f"Sunday in {get_liturgical_season(target_date)}",
            "rank": "Sunday",
            "color": get_liturgical_color(target_date),
        }

    return {
        "date": target_date.isoformat(),
        "liturgical_year": get_liturgical_year(target_date),
        "season": get_liturgical_season(target_date),
        "color": celebration["color"] if celebration else get_liturgical_color(target_date),
        "celebration": celebration["name"] if celebration else "Weekday",
        "rank": celebration["rank"] if celebration else "Weekday",
    }

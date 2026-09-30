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
    The liturgical year begins with the First Sunday of Advent.
    """
    # Find the start of the current liturgical year (Advent)
    # The First Sunday of Advent is the Sunday closest to Nov 30th
    
    # Simple approximation for now - needs refinement for production
    # A year is A if (target_date.year - 2022) % 3 == 0 (roughly)
    # Actually, we should check against Advent start date.
    
    # For now, stick to the cycle logic, but be aware it needs to handle the Advent shift
    # The liturgical year A, B, C is based on the Advent start date.
    # The year before the year of our Lord 2023 was A (since 2022 was C, 2023 was A).
    # Wait, Advent of 2022 starts Year A. So (target_date.year + 1) % 3?
    # Let's use a standard lookup or robust calculation.
    # 2025-11-30 is Advent 2025 (Year C). Wait. 
    # Let's trust the existing logic or refine it to be robust based on known dates.
    
    # Let's use a simpler, reliable way:
    # 2025 is Year C, 2026 is Year A, 2027 is Year B.
    # (year - 2026) % 3 == 0 -> A.
    
    # Liturgical year starts in Advent. 
    # If target_date is before Advent, it's the *current* liturgical year.
    # If target_date is in Advent, it's the *new* liturgical year.
    
    advent_start = get_advent_start(target_date.year)
    if target_date < advent_start:
        # Before Advent, use previous liturgical year cycle
        year_to_check = target_date.year
    else:
        # In Advent, use new liturgical year cycle
        year_to_check = target_date.year + 1
        
    # Standard: 2025-11-30 starts Year C? No, 2024 is B, 2025 is C, 2026 is A.
    # (2026 - 2026) % 3 = 0 -> A
    cycle = (year_to_check - 2026) % 3
    if cycle == 0: return "A"
    if cycle == 1: return "B"
    return "C"

def get_advent_start(year: int) -> date:
    # Sunday closest to Nov 30
    # Nov 30 is the reference.
    # Find weekday of Nov 30.
    nov30 = date(year, 11, 30)
    weekday = nov30.weekday()
    # Sunday is 6.
    # Advent start is the Sunday on or before Nov 30 (which is the Sunday closest).
    # Actually, it's the Sunday on or before Nov 30? No, it's the Sunday on or before Nov 30 is not necessarily closest.
    # The rule is: Sunday closest to Nov 30.
    
    # If nov30 is Monday (0), Sunday before is Sunday 29.
    # If nov30 is Tuesday (1), Sunday before is Sunday 28.
    # ...
    # If nov30 is Sunday (6), it is Nov 30.
    
    days_until_sunday = (6 - weekday) % 7
    # If sunday is 6, 6-6=0.
    # Advent is the Sunday closest.
    
    # Actually, let's use a simpler, robust formula.
    # Advent starts on the 4th Sunday before Christmas.
    christmas = date(year, 12, 25)
    # The 4th Sunday before Dec 25.
    # Christmas is Dec 25.
    # The Sunday before Dec 25 is: 25 - ((25 - 0 (Sunday is not 0?)) 
    # Let's just find the first Sunday of Advent properly.
    
    # 4 weeks = 28 days.
    # It is the Sunday closest to Nov 30th.
    
    days_to_sunday = (6 - nov30.weekday()) % 7
    # If Sunday is 6, 6-6 = 0.
    # If Monday is 0, 6-0 = 6 days after (Sunday is Nov 29). 
    # Wait, the Sunday closest to Nov 30.
    
    # Let's refine the Advent start.
    # Advent start is the Sunday which is closest to Nov 30.
    # (30 - X) / 7 -> closest Sunday
    
    # This is fine for a helper.
    return nov30 + timedelta(days=days_to_sunday - 7 if days_to_sunday > 3 else days_to_sunday)


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
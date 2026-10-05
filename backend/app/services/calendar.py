from datetime import date, datetime, timedelta, timezone
from typing import Optional
import re
from zoneinfo import ZoneInfo


KENYA_TIMEZONE = ZoneInfo("Africa/Nairobi")


def kenya_today(now: datetime | None = None) -> date:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(KENYA_TIMEZONE).date()


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


def get_liturgical_year_sunday(target_date: date) -> str:
    """Return the Sunday lectionary cycle (A/B/C) in effect on a Gregorian date."""
    year_of_cycle = target_date.year + (target_date >= get_advent_start(target_date.year))
    return ("A", "B", "C")[(year_of_cycle - 2026) % 3]


def get_liturgical_year_weekday(target_date: date) -> str:
    """Return the weekday lectionary cycle (I/II) in effect on a Gregorian date."""
    # Odd years: Cycle I, Even years: Cycle II
    year_of_cycle = target_date.year + (target_date >= get_advent_start(target_date.year))
    return "I" if year_of_cycle % 2 == 1 else "II"


def get_liturgical_year(target_date: date) -> str:
    """Return the Sunday lectionary cycle (A/B/C) for a Gregorian date.

    Backwards-compatible alias for :func:`get_liturgical_year_sunday`.

    The lectionary runs two independent cycles: a three-year Sunday cycle
    (A/B/C) and a two-year weekday cycle (I/II). They were previously reported
    through a single ``liturgical_year`` value, which could only ever have
    described the Sunday cycle. Callers that genuinely need the weekday cycle
    must call :func:`get_liturgical_year_weekday` explicitly.

    This alias is retained so existing callers -- notably
    ``app.services.lectionary_engine`` -- continue to work unchanged.
    """
    return get_liturgical_year_sunday(target_date)


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


def get_liturgical_week(target_date: date) -> Optional[int]:
    """Calculate the week number within the liturgical season."""
    season = get_liturgical_season(target_date)
    easter = easter_sunday(target_date.year)
    ash_wednesday = easter - timedelta(days=46)
    pentecost = easter + timedelta(days=49)
    advent_start = get_advent_start(target_date.year)
    christmas_end = _baptism_of_the_lord(target_date.year)
    
    if season == "Advent":
        # Weeks in Advent start from Advent Sunday
        days_since_advent = (target_date - advent_start).days
        return (days_since_advent // 7) + 1
    
    if season == "Christmas":
        # Week 1: Dec 25 to end of year
        # Week 2+: Start of year to Baptism of Lord
        if target_date.month == 12:
            return 1
        days_since_new_year = (target_date - date(target_date.year, 1, 1)).days
        return (days_since_new_year // 7) + 2
    
    if season == "Lent":
        # Weeks in Lent: from Ash Wednesday to Holy Thursday
        days_since_ash = (target_date - ash_wednesday).days
        return (days_since_ash // 7) + 1
    
    if season == "Holy Week":
        return 6  # Special designation
    
    if season == "Triduum":
        return 6  # Part of Holy Week
    
    if season == "Easter":
        # Weeks in Easter season: from Easter Sunday to Pentecost
        days_since_easter = (target_date - easter).days
        return (days_since_easter // 7) + 1
    
    if season == "Ordinary Time":
        # Ordinary Time is split:
        # Weeks 1-9: After Christmas to Ash Wednesday
        # Weeks 10-34: After Pentecost to Advent
        previous_advent = get_advent_start(target_date.year - 1)
        if ash_wednesday > target_date > christmas_end:
            # First period of Ordinary Time
            days_since_baptism = (target_date - christmas_end).days
            return (days_since_baptism // 7) + 1
        else:
            # Second period of Ordinary Time
            days_since_pentecost = (target_date - pentecost).days
            # Calculate weeks from previous Ordinary Time period
            week = (days_since_pentecost // 7) + 10
            return week if week <= 34 else 34
    
    return None


def get_liturgical_color(target_date: date) -> str:
    """Get liturgical color with special cases for Rose and Black."""
    easter = easter_sunday(target_date.year)
    ash_wednesday = easter - timedelta(days=46)
    palm_sunday = easter - timedelta(days=7)
    
    # Gaudete Sunday (Third Sunday of Advent)
    advent_start = get_advent_start(target_date.year)
    gaudete_sunday = advent_start + timedelta(days=14)
    if target_date == gaudete_sunday:
        return "Rose"
    
    # Laetare Sunday (Fourth Sunday of Lent)
    laetare_sunday = ash_wednesday + timedelta(days=25)
    if target_date == laetare_sunday:
        return "Rose"
    
    # Good Friday
    if target_date == easter - timedelta(days=2):
        return "Black"
    
    # Holy Thursday (before Mass: Red, after Mass: White)
    if target_date == easter - timedelta(days=3):
        return "White"  # After Mass is more common
    
    # Palm Sunday
    if target_date == palm_sunday:
        return "Red"
    
    # Pentecost
    if target_date == easter + timedelta(days=49):
        return "Red"
    
    season = get_liturgical_season(target_date)
    if season == "Holy Week" and target_date.weekday() == 6:
        return "Red"
    
    return LITURGICAL_COLORS.get(season, "Green")


# General Roman Calendar Celebrations
GENERAL_CELEBRATIONS = {
    (1, 1): {"name": "Solemnity of Mary, Mother of God", "rank": "Solemnity", "color": "White"},
    (1, 6): {"name": "Epiphany of the Lord", "rank": "Solemnity", "color": "White"},
    (2, 2): {"name": "Presentation of the Lord", "rank": "Feast", "color": "White"},
    (3, 19): {"name": "Saint Joseph, Spouse of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (3, 25): {"name": "Annunciation of the Lord", "rank": "Solemnity", "color": "White"},
    (6, 24): {"name": "Nativity of Saint John the Baptist", "rank": "Solemnity", "color": "White"},
    (6, 29): {"name": "Saints Peter and Paul, Apostles", "rank": "Solemnity", "color": "Red"},
    (8, 6): {"name": "Transfiguration of the Lord", "rank": "Feast", "color": "White"},
    (8, 15): {"name": "Assumption of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (9, 14): {"name": "Exaltation of the Holy Cross", "rank": "Feast", "color": "Red"},
    (9, 29): {"name": "Saints Michael, Gabriel, and Raphael, Archangels", "rank": "Feast", "color": "White"},
    (9, 30): {"name": "Saint Jerome, Priest and Doctor of the Church", "rank": "Memorial", "color": "White"},
    (10, 10): {"name": "Saint Daniel Comboni, Bishop", "rank": "Memorial", "color": "White"},
    (11, 1): {"name": "All Saints", "rank": "Solemnity", "color": "White"},
    (11, 2): {"name": "All Souls", "rank": "Commemoration", "color": "Purple"},
    (12, 8): {"name": "Immaculate Conception of the Blessed Virgin Mary", "rank": "Solemnity", "color": "White"},
    (12, 25): {"name": "Nativity of the Lord", "rank": "Solemnity", "color": "White"},
}

# Kenya National Calendar additions
# Based on authoritative sources: General Roman Calendar with national proper additions
KENYA_CELEBRATIONS = {
    # October 20: Blessed Daudi Okelo and Jildo Irwa, martyrs (Kenya/Uganda)
    # Reference: Universalis Kenya calendar, GCatholic.org
    # These are beatified (not yet canonized), rank is Optional Memorial
    (10, 20): {"name": "Blessed Daudi Okelo and Jildo Irwa, martyrs", "rank": "Optional Memorial", "color": "Red"},
    # Saint Daniel Comboni is in the General Roman Calendar as a Memorial (October 10)
    # It is NOT Kenya-specific, so it should not be in KENYA_CELEBRATIONS
    # It's already in GENERAL_CELEBRATIONS with correct rank
}


def get_celebration(target_date: date, region: str = "KE") -> Optional[dict[str, str]]:
    """Get celebration for a date, considering regional calendars."""
    # Check for Christ the King (last Sunday before Advent)
    advent_start = get_advent_start(target_date.year)
    # Christ the King is the Sunday immediately before Advent
    christ_king = advent_start - timedelta(days=7)
    if target_date == christ_king:
        return {"name": "Our Lord Jesus Christ, King of the Universe", "rank": "Solemnity", "color": "White"}
    
    # Check regional celebrations first
    if region == "KE":
        kenya_celebration = KENYA_CELEBRATIONS.get((target_date.month, target_date.day))
        if kenya_celebration:
            return kenya_celebration
    
    # Check general Roman calendar
    general_celebration = GENERAL_CELEBRATIONS.get((target_date.month, target_date.day))
    if general_celebration:
        # Solemnity precedence: if a solemnity falls on a Sunday, it takes precedence
        # (The Sunday is suppressed or the solemnity is transferred in some cases)
        # For our purposes, the solemnity wins
        if general_celebration["rank"] == "Solemnity" and target_date.weekday() == 6:
            return general_celebration
        return general_celebration

    # Check movable celebrations
    easter = easter_sunday(target_date.year)
    relative = {
        easter - timedelta(days=46): {"name": "Ash Wednesday", "rank": "Feria", "color": "Purple"},
        easter - timedelta(days=7): {"name": "Palm Sunday of the Passion of the Lord", "rank": "Sunday", "color": "Red"},
        easter: {"name": "Easter Sunday", "rank": "Solemnity", "color": "White"},
        easter + timedelta(days=39): {"name": "Ascension of the Lord", "rank": "Solemnity", "color": "White"},
        easter + timedelta(days=49): {"name": "Pentecost Sunday", "rank": "Solemnity", "color": "Red"},
        easter + timedelta(days=56): {"name": "Most Holy Trinity", "rank": "Solemnity", "color": "White"},
        easter + timedelta(days=60): {"name": "Most Holy Body and Blood of Christ", "rank": "Solemnity", "color": "White"},
        easter + timedelta(days=4 * 7 + 4): {"name": "Sacred Heart of Jesus", "rank": "Solemnity", "color": "White"},
    }
    if target_date in relative:
        return relative[target_date]
    
    return None


def get_calendar_info(target_date: date, region: str = "KE") -> dict[str, str]:
    """Get comprehensive calendar information for a date."""
    celebration = get_celebration(target_date, region)
    
    # Determine celebration name and rank
    if celebration:
        celebration_name = celebration["name"]
        celebration_rank = celebration["rank"]
        liturgical_color = celebration["color"]
    elif target_date.weekday() == 6:
        celebration_name = f"Sunday in {get_liturgical_season(target_date)}"
        celebration_rank = "Sunday"
        liturgical_color = get_liturgical_color(target_date)
    else:
        celebration_name = "Weekday"
        celebration_rank = "Feria"
        liturgical_color = get_liturgical_color(target_date)

    return {
        "date": target_date.isoformat(),
        "sunday_cycle": get_liturgical_year_sunday(target_date),
        "weekday_cycle": get_liturgical_year_weekday(target_date),
        "season": get_liturgical_season(target_date),
        "week": get_liturgical_week(target_date),
        "color": liturgical_color,
        "celebration": celebration_name,
        "rank": celebration_rank,
        "region": region,
    }

"""Tests for liturgical calendar engine."""
import pytest
from datetime import date, timedelta
from app.services.calendar import (
    get_advent_start,
    get_liturgical_year_sunday,
    get_liturgical_year_weekday,
    easter_sunday,
    get_liturgical_season,
    get_liturgical_week,
    get_liturgical_color,
    get_celebration,
    get_calendar_info,
)


class TestEasterSunday:
    """Test Easter Sunday calculation."""
    
    def test_easter_2024(self):
        """Known Easter dates."""
        # 2024: March 31
        assert easter_sunday(2024) == date(2024, 3, 31)
    
    def test_easter_2025(self):
        """2025: April 20"""
        assert easter_sunday(2025) == date(2025, 4, 20)
    
    def test_easter_2026(self):
        """2026: April 5"""
        assert easter_sunday(2026) == date(2026, 4, 5)


class TestLiturgicalYear:
    """Test liturgical year calculation."""
    
    def test_sunday_cycle_2026(self):
        """2026 is Year A until Advent, then B."""
        # Advent 2026 starts the next cycle
        advent_start = get_advent_start(2026)
        assert get_liturgical_year_sunday(date(2026, 1, 1)) == "A"
        assert get_liturgical_year_sunday(advent_start - timedelta(days=1)) == "A"
        assert get_liturgical_year_sunday(advent_start) == "B"
    
    def test_sunday_cycle_2027(self):
        """2027 is Year B until Advent, then C."""
        assert get_liturgical_year_sunday(date(2027, 1, 1)) == "B"
    
    def test_weekday_cycle_2026(self):
        """Weekday cycle is based on year of cycle."""
        # 2026 liturgical year starts Nov 2025
        # So 2026 is an even year of the cycle -> Cycle II
        assert get_liturgical_year_weekday(date(2026, 1, 1)) == "II"
    
    def test_weekday_cycle_2027(self):
        """2027 is odd year of the cycle -> Cycle I."""
        assert get_liturgical_year_weekday(date(2027, 1, 1)) == "I"


class TestLiturgicalSeason:
    """Test liturgical season determination."""
    
    def test_advent_2026(self):
        """Advent 2026 starts in late November."""
        advent_start = get_advent_start(2026)
        assert get_liturgical_season(advent_start) == "Advent"
        assert get_liturgical_season(advent_start + timedelta(days=6)) == "Advent"
    
    def test_christmas_season(self):
        """Christmas season includes Christmas and early January."""
        assert get_liturgical_season(date(2026, 12, 25)) == "Christmas"
        assert get_liturgical_season(date(2027, 1, 1)) == "Christmas"
    
    def test_lent_2026(self):
        """Lent 2026 (before Easter)."""
        easter = easter_sunday(2026)
        ash_wednesday = easter - timedelta(days=46)
        assert get_liturgical_season(ash_wednesday) == "Lent"
        assert get_liturgical_season(ash_wednesday + timedelta(days=20)) == "Lent"
    
    def test_easter_season_2026(self):
        """Easter season 2026."""
        easter = easter_sunday(2026)
        assert get_liturgical_season(easter) == "Easter"
        assert get_liturgical_season(easter + timedelta(days=20)) == "Easter"
        pentecost = easter + timedelta(days=49)
        assert get_liturgical_season(pentecost) == "Easter"
    
    def test_ordinary_time(self):
        """Ordinary Time outside other seasons."""
        assert get_liturgical_season(date(2026, 6, 15)) == "Ordinary Time"
        assert get_liturgical_season(date(2026, 9, 15)) == "Ordinary Time"


class TestLiturgicalWeek:
    """Test liturgical week calculation."""
    
    def test_advent_weeks(self):
        """Week numbers in Advent."""
        advent_start = get_advent_start(2026)
        assert get_liturgical_week(advent_start) == 1
        assert get_liturgical_week(advent_start + timedelta(days=7)) == 2
    
    def test_ordinary_time_weeks(self):
        """Week numbers in Ordinary Time."""
        # This is a basic test - the algorithm is complex
        week = get_liturgical_week(date(2026, 9, 28))
        assert week is not None
        assert 1 <= week <= 34


class TestLiturgicalColor:
    """Test liturgical color determination."""
    
    def test_advent_color(self):
        """Advent is Purple."""
        advent_start = get_advent_start(2026)
        assert get_liturgical_color(advent_start) == "Purple"
    
    def test_christmas_color(self):
        """Christmas is White."""
        assert get_liturgical_color(date(2026, 12, 25)) == "White"
    
    def test_lent_color(self):
        """Lent is Purple."""
        easter = easter_sunday(2026)
        ash_wednesday = easter - timedelta(days=46)
        assert get_liturgical_color(ash_wednesday) == "Purple"
    
    def test_palm_sunday_color(self):
        """Palm Sunday is Red."""
        easter = easter_sunday(2026)
        palm_sunday = easter - timedelta(days=7)
        assert get_liturgical_color(palm_sunday) == "Red"
    
    def test_easter_sunday_color(self):
        """Easter Sunday is White."""
        easter = easter_sunday(2026)
        assert get_liturgical_color(easter) == "White"
    
    def test_ordinary_time_color(self):
        """Ordinary Time is Green."""
        assert get_liturgical_color(date(2026, 6, 15)) == "Green"


class TestCelebrations:
    """Test fixed and movable celebrations."""
    
    def test_christmas(self):
        """Christmas Solemnity."""
        celebration = get_celebration(date(2026, 12, 25))
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
        assert celebration["color"] == "White"
    
    def test_epiphany(self):
        """Epiphany Solemnity."""
        celebration = get_celebration(date(2026, 1, 6))
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
    
    def test_all_saints(self):
        """All Saints Solemnity."""
        celebration = get_celebration(date(2026, 11, 1))
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
    
    def test_st_michael_archangels(self):
        """Saints Michael, Gabriel, Raphael - Feast."""
        celebration = get_celebration(date(2026, 9, 29))
        assert celebration is not None
        assert celebration["rank"] == "Feast"
        assert celebration["color"] == "White"
    
    def test_st_jerome(self):
        """Saint Jerome - Memorial."""
        celebration = get_celebration(date(2026, 9, 30))
        assert celebration is not None
        assert celebration["rank"] == "Memorial"
    
    def test_st_daniel_comboni(self):
        """Saint Daniel Comboni - Memorial (General Roman Calendar)."""
        celebration = get_celebration(date(2026, 10, 10), region="KE")
        assert celebration is not None
        assert celebration["rank"] == "Memorial"
    
    def test_blessed_daudi_okelo_jildo_irwa(self):
        """Blessed Daudi Okelo and Jildo Irwa - Optional Memorial (Kenya proper)."""
        celebration = get_celebration(date(2026, 10, 20), region="KE")
        assert celebration is not None
        assert celebration["rank"] == "Optional Memorial"
        assert "Daudi Okelo" in celebration["name"] or "Okelo" in celebration["name"]
    
    def test_solemnity_on_sunday_precedence(self):
        """Solemnity takes precedence when falling on a Sunday."""
        # Find a solemnity that falls on a Sunday (e.g., Feast of Sts Peter and Paul June 29)
        # In 2026, June 29 is a Monday, so test with a different year
        # December 8 (Immaculate Conception) is a solemnity
        # In 2024, December 8 is a Sunday
        celebration = get_celebration(date(2024, 12, 8))
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
        assert "Immaculate Conception" in celebration["name"]
    
    def test_ash_wednesday(self):
        """Ash Wednesday (movable)."""
        easter = easter_sunday(2026)
        ash_wednesday = easter - timedelta(days=46)
        celebration = get_celebration(ash_wednesday)
        assert celebration is not None
        assert celebration["rank"] == "Feria"
        assert celebration["color"] == "Purple"
    
    def test_easter_sunday(self):
        """Easter Sunday (movable)."""
        easter = easter_sunday(2026)
        celebration = get_celebration(easter)
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
        assert celebration["color"] == "White"
    
    def test_pentecost(self):
        """Pentecost Sunday (movable)."""
        easter = easter_sunday(2026)
        pentecost = easter + timedelta(days=49)
        celebration = get_celebration(pentecost)
        assert celebration is not None
        assert celebration["rank"] == "Solemnity"
        assert celebration["color"] == "Red"


class TestCalendarInfo:
    """Test complete calendar information."""
    
    def test_2026_09_28(self):
        """September 28, 2026 - Monday of week 26 in Ordinary Time."""
        info = get_calendar_info(date(2026, 9, 28), region="KE")
        
        assert info["date"] == "2026-09-28"
        assert info["sunday_cycle"] == "A"
        assert info["weekday_cycle"] == "II"  # 2026 is even year of cycle
        assert info["season"] == "Ordinary Time"
        assert info["color"] == "Green"
        assert info["rank"] == "Feria"  # Monday
    
    def test_2026_09_29(self):
        """September 29, 2026 - Saints Michael, Gabriel, Raphael."""
        info = get_calendar_info(date(2026, 9, 29), region="KE")
        
        assert info["date"] == "2026-09-29"
        assert info["celebration"] == "Saints Michael, Gabriel, and Raphael, Archangels"
        assert info["rank"] == "Feast"
        assert info["color"] == "White"
    
    def test_2026_09_30(self):
        """September 30, 2026 - Saint Jerome."""
        info = get_calendar_info(date(2026, 9, 30), region="KE")
        
        assert info["date"] == "2026-09-30"
        assert info["celebration"] == "Saint Jerome, Priest and Doctor of the Church"
        assert info["rank"] == "Memorial"
        assert info["color"] == "White"
    
    def test_2026_10_10(self):
        """October 10, 2026 - Saint Daniel Comboni (General Roman Calendar Memorial)."""
        info = get_calendar_info(date(2026, 10, 10), region="KE")
        
        assert info["date"] == "2026-10-10"
        assert info["celebration"] == "Saint Daniel Comboni, Bishop"
        assert info["rank"] == "Memorial"
        assert info["color"] == "White"
    
    def test_2026_10_20(self):
        """October 20, 2026 - Blessed Daudi Okelo and Jildo Irwa (Kenya proper Optional Memorial)."""
        info = get_calendar_info(date(2026, 10, 20), region="KE")
        
        assert info["date"] == "2026-10-20"
        assert "Daudi Okelo" in info["celebration"] or "Okelo" in info["celebration"]
        assert info["rank"] == "Optional Memorial"
        assert info["color"] == "Red"
    
    def test_presentation_of_the_lord(self):
        """February 2 - Presentation of the Lord."""
        info = get_calendar_info(date(2026, 2, 2))
        assert info["celebration"] == "Presentation of the Lord"
        assert info["rank"] == "Feast"
        assert info["color"] == "White"
    
    def test_christ_the_king(self):
        """Christ the King - Sunday before Advent (7 days prior)."""
        # For 2026, Advent starts Nov 29, so Christ the King is Nov 22
        info = get_calendar_info(date(2026, 11, 22))
        # Nov 22, 2026 is a Sunday, should be Christ the King
        assert info["celebration"] == "Our Lord Jesus Christ, King of the Universe"
        assert info["rank"] == "Solemnity"
        assert info["color"] == "White"
    
    def test_rose_color_gaudete(self):
        """Gaudete Sunday - Rose color."""
        # For 2026, Advent starts Nov 29, so Gaudete is Dec 13
        info = get_calendar_info(date(2026, 12, 13))
        assert info["color"] == "Rose"
    
    def test_rose_color_laetare(self):
        """Laetare Sunday - Rose color."""
        # For 2026, Ash Wednesday is Feb 18, so Laetare is March 15 (4th Sunday of Lent)
        info = get_calendar_info(date(2026, 3, 15))
        # Verify it's a Sunday
        assert date(2026, 3, 15).weekday() == 6
        assert info["color"] == "Rose"
    
    def test_black_color_good_friday(self):
        """Good Friday - Black color."""
        # Good Friday 2026 is April 3
        info = get_calendar_info(date(2026, 4, 3))
        assert info["color"] == "Black"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

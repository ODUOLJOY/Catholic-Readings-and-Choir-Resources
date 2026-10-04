"""Tests for reading reference parsing."""
import pytest
from app.services.universalis_parser import UniversalisParser


def test_parse_simple_reference():
    """Test parsing a simple chapter:verse reference."""
    ref = "Galatians 3:22-29"
    parsed = UniversalisParser.parse_reference(ref)
    
    assert parsed["book"] == "Galatians"
    assert parsed["chapter_start"] == 3
    assert parsed["verse_start"] == "22-29"  # Full verse range preserved
    assert parsed["verse_end"] == "22-29"
    assert parsed["display_reference"] == "Galatians 3:22-29"


def test_parse_psalm_with_variant():
    """Test parsing Psalm with alternative numbering."""
    ref = "Psalm 104(105):2-7"
    parsed = UniversalisParser.parse_reference(ref)
    
    assert parsed["book"] == "Psalm"
    assert parsed["chapter_start"] == 104
    assert parsed["psalm_number_variant"] == "105"
    assert parsed["verse_start"] == "2-7"
    assert parsed["verse_end"] == "2-7"


def test_parse_multiple_verse_ranges():
    """Test parsing reference with multiple verse ranges."""
    ref = "Daniel 7:9-10,13-14"
    parsed = UniversalisParser.parse_reference(ref)
    
    assert parsed["book"] == "Daniel"
    assert parsed["chapter_start"] == 7
    assert parsed["verse_start"] == "9-10,13-14"
    assert parsed["verse_end"] == "9-10,13-14"


def test_parse_1_corinthians():
    """Test parsing book number prefix."""
    ref = "1 Corinthians 12:12-14,27-31"
    parsed = UniversalisParser.parse_reference(ref)
    
    assert parsed["book"] == "1 Corinthians"
    assert parsed["chapter_start"] == 12
    assert parsed["verse_start"] == "12-14,27-31"


def test_parse_celebration_rank():
    """Test celebration rank parsing."""
    assert UniversalisParser.parse_celebration_rank("Solemnity") == "Solemnity"
    assert UniversalisParser.parse_celebration_rank("Feast") == "Feast"
    assert UniversalisParser.parse_celebration_rank("Memorial") == "Memorial"
    assert UniversalisParser.parse_celebration_rank("Obligatory Memorial") == "Memorial (Obligatory)"
    assert UniversalisParser.parse_celebration_rank("Feria") == "Feria"
    assert UniversalisParser.parse_celebration_rank("Sunday") == "Sunday"


def test_reading_type_mapping():
    """Test reading type mapping."""
    assert UniversalisParser.READING_TYPES["First reading"] == "FIRST_READING"
    assert UniversalisParser.READING_TYPES["Responsorial Psalm"] == "RESPONSORIAL_PSALM"
    assert UniversalisParser.READING_TYPES["Gospel"] == "GOSPEL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

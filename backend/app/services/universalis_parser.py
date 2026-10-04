"""Universalis data parser for liturgical calendar import."""
import re
from typing import Dict


class UniversalisParser:
    """Parse Universalis liturgical data."""
    
    # Reading type mapping
    READING_TYPES = {
        "First reading": "FIRST_READING",
        "Responsorial Psalm": "RESPONSORIAL_PSALM",
        "Second reading": "SECOND_READING",
        "Gospel Acclamation": "GOSPEL_ACCLAMATION",
        "Gospel": "GOSPEL",
        "Alleluia": "GOSPEL_ACCLAMATION",
    }
    
    @staticmethod
    def parse_reference(reference: str) -> Dict:
        """
        Parse a scripture reference into structured components.
        
        Examples:
            "Galatians 3:22-29" -> {"book": "Galatians", "chapter_start": 3, "verse_start": "22-29", "chapter_end": 3, "verse_end": "22-29"}
            "Psalm 104(105):2-7" -> {"book": "Psalm", "chapter_start": 104, "verse_start": "2-7", "chapter_end": 104, "verse_end": "2-7", "psalm_number_variant": "105"}
            "Daniel 7:9-10,13-14" -> {"book": "Daniel", "chapter_start": 7, "verse_start": "9-10,13-14", "chapter_end": 7, "verse_end": "9-10,13-14"}
        """
        result = {
            "book": None,
            "chapter_start": None,
            "verse_start": None,
            "chapter_end": None,
            "verse_end": None,
            "display_reference": reference,
            "psalm_number_variant": None,
        }
        
        # Check for Psalm variant (e.g., Psalm 104(105))
        psalm_match = re.match(r'Psalm\s+(\d+)\((\d+)\)', reference)
        if psalm_match:
            result["book"] = "Psalm"
            result["chapter_start"] = int(psalm_match.group(1))
            result["psalm_number_variant"] = psalm_match.group(2)
            # Extract the verse part after the colon
            verse_match = re.search(r':(.+)$', reference)
            if verse_match:
                verses = verse_match.group(1).strip()
                result["verse_start"] = verses
                result["verse_end"] = verses
                result["chapter_end"] = result["chapter_start"]
            return result
        
        # Extract book (everything before the number/colon)
        # Handle cases like "1 Corinthians" or "2 Timothy"
        book_match = re.match(r'^([0-9]*\s*[A-Za-z]+)\s+', reference)
        if book_match:
            result["book"] = book_match.group(1).strip()
            remaining = reference[len(book_match.group(0)):]
        else:
            # Fallback: book is first word
            parts = reference.split()
            if parts:
                result["book"] = parts[0]
                remaining = reference[len(parts[0]) + 1:]
            else:
                remaining = reference
        
        # Parse chapter and verse
        # Pattern: chapter:verse or chapter:verse-verse
        verse_match = re.search(r'(\d+):(.+)', remaining)
        if verse_match:
            if result["chapter_start"] is None:
                result["chapter_start"] = int(verse_match.group(1))
            verses = verse_match.group(2)
            
            # Parse verse range - preserve the full verse range including commas
            # The verse field can contain "9-10,13-14" which we want to preserve
            result["verse_start"] = verses.strip()
            result["verse_end"] = verses.strip()
            result["chapter_end"] = result["chapter_start"]
        
        return result
    
    @staticmethod
    def parse_celebration_rank(rank_text: str) -> str:
        """Convert Universalis rank text to our standard ranks."""
        rank_lower = rank_text.lower()
        
        if "solemnity" in rank_lower:
            return "Solemnity"
        elif "feast" in rank_lower:
            return "Feast"
        elif "memorial" in rank_lower:
            if "obligatory" in rank_lower or "required" in rank_lower:
                return "Memorial (Obligatory)"
            return "Memorial"
        elif "feria" in rank_lower:
            return "Feria"
        elif "sunday" in rank_lower:
            return "Sunday"
        else:
            return "Commemoration"

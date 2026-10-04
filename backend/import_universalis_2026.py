"""
Import 2026 Kenya liturgical calendar from Universalis.

This script fetches liturgical data from Universalis Kenya API and
imports it as structured reading references (no Bible text).

Usage:
    python import_universalis_2026.py --region KE --year 2026
"""
import argparse
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import requests
from sqlalchemy.orm import sessionmaker
from app.db.database import engine
from app.services.liturgical_sync import LiturgicalSyncService
from app.services.universalis_parser import UniversalisParser


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
            "Galatians 3:22-29" -> {"book": "Galatians", "chapter_start": 3, "verse_start": "22", "chapter_end": 3, "verse_end": "29"}
            "Psalm 104(105):2-7" -> {"book": "Psalm", "chapter_start": 104, "verse_start": "2", "chapter_end": 104, "verse_end": "7", "psalm_number_variant": "105"}
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
            result["chapter_start"] = int(verse_match.group(1))
            verses = verse_match.group(2)
            
            # Check for Psalm variant (e.g., 104(105))
            psalm_variant = re.search(r'(\d+)\((\d+)\)', result["book"])
            if psalm_variant:
                result["book"] = "Psalm"
                result["chapter_start"] = int(psalm_variant.group(1))
                result["psalm_number_variant"] = psalm_variant.group(2)
            
            # Parse verse range
            if '-' in verses:
                start_end = verses.split('-')
                result["verse_start"] = start_end[0].strip()
                result["verse_end"] = start_end[1].strip()
                result["chapter_end"] = result["chapter_start"]
            else:
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


class UniversalisImporter:
    """Import liturgical data from Universalis."""
    
    BASE_URL = "https://universalis.com"
    
    def __init__(self, region: str = "KE"):
        self.region = region
        self.session = sessionmaker(bind=engine)()
    
    def fetch_date(self, target_date: date) -> Dict:
        """Fetch liturgical data for a specific date from Universalis."""
        # Universalis JSONP endpoint
        url = f"{self.BASE_URL}/{self.region}/{target_date.strftime('%Y%m%d')}/jsonp.js"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse JSONP response (format: callback({...}))
            jsonp_text = response.text
            json_start = jsonp_text.find('(')
            json_end = jsonp_text.rfind(')')
            
            if json_start != -1 and json_end != -1:
                json_text = jsonp_text[json_start + 1:json_end]
                import json
                data = json.loads(json_text)
                return self._parse_universalis_data(data, target_date)
            
        except Exception as e:
            print(f"Error fetching {target_date}: {e}")
        
        return {}
    
    def _parse_universalis_data(self, data: Dict, target_date: date) -> Dict:
        """Parse Universalis JSON response into our schema."""
        # Extract celebration info
        celebration = data.get("celebration", {})
        
        # Extract reading references
        readings = data.get("readings", {})
        
        # Build reading sets
        reading_sets = []
        
        # Primary reading set (weekday/feria readings)
        primary_set = {
            "type": "daily",
            "selection_status": "weekday_default",
            "readings": []
        }
        
        # Parse first reading
        if "first_reading" in readings:
            ref = self._parse_reading(readings["first_reading"], "FIRST_READING")
            if ref:
                primary_set["readings"].append(ref)
        
        # Parse responsorial psalm
        if "psalm" in readings:
            ref = self._parse_reading(readings["psalm"], "RESPONSORIAL_PSALM")
            if ref:
                primary_set["readings"].append(ref)
        
        # Parse second reading (Sundays only)
        if "second_reading" in readings:
            ref = self._parse_reading(readings["second_reading"], "SECOND_READING")
            if ref:
                primary_set["readings"].append(ref)
        
        # Parse gospel
        if "gospel" in readings:
            ref = self._parse_reading(readings["gospel"], "GOSPEL")
            if ref:
                primary_set["readings"].append(ref)
        
        reading_sets.append(primary_set)
        
        # Proper reading set (if celebration has proper readings)
        if "proper_readings" in data:
            proper_set = {
                "type": "proper",
                "selection_status": "strictly_proper",
                "celebration_name": celebration.get("name"),
                "readings": []
            }
            
            for reading_type, reference in data["proper_readings"].items():
                ref = self._parse_reading(reference, self._map_reading_type(reading_type))
                if ref:
                    proper_set["readings"].append(ref)
            
            if proper_set["readings"]:
                reading_sets.append(proper_set)
        
        return {
            "date": target_date.isoformat(),
            "region": self.region,
            "celebration": celebration.get("name", "Weekday"),
            "rank": UniversalisParser.parse_celebration_rank(celebration.get("rank", "Feria")),
            "liturgical_color": celebration.get("color", "Green"),
            "sunday_cycle": data.get("sunday_cycle", "A"),
            "weekday_cycle": data.get("weekday_cycle", "I"),
            "season": data.get("season", "Ordinary Time"),
            "week": data.get("week"),
            "source": "Universalis",
            "source_record_id": f"{self.region}_{target_date.isoformat()}",
            "reading_sets": reading_sets,
        }
    
    def _parse_reading(self, reference: str, reading_type: str) -> Optional[Dict]:
        """Parse a single reading reference."""
        if not reference:
            return None
        
        parsed = UniversalisParser.parse_reference(reference)
        parsed["type"] = reading_type
        parsed["is_primary"] = True
        parsed["is_alternative"] = False
        parsed["is_optional"] = False
        parsed["sequence"] = 0
        
        return parsed
    
    def _map_reading_type(self, universalis_type: str) -> str:
        """Map Universalis reading type to our standard types."""
        return UniversalisParser.READING_TYPES.get(
            universalis_type,
            universalis_type.upper().replace(' ', '_')
        )
    
    def import_year(self, year: int):
        """Import entire year from Universalis."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        stats = {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
        }
        
        target_date = start_date
        while target_date <= end_date:
            try:
                data = self.fetch_date(target_date)
                if data:
                    LiturgicalSyncService.import_verified_data(self.session, data)
                    stats["imported"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                print(f"Error importing {target_date}: {e}")
                stats["errors"] += 1
            
            stats["total"] += 1
            target_date += timedelta(days=1)
            
            # Commit every 10 days
            if stats["total"] % 10 == 0:
                self.session.commit()
        
        self.session.commit()
        print(f"Import complete for {year}: {stats}")
        return stats


def main():
    parser = argparse.ArgumentParser(description="Import Universalis liturgical calendar")
    parser.add_argument("--region", default="KE", help="Region code (default: KE)")
    parser.add_argument("--year", type=int, default=2026, help="Year to import (default: 2026)")
    parser.add_argument("--date", help="Specific date to import (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    importer = UniversalisImporter(region=args.region)
    
    if args.date:
        target_date = date.fromisoformat(args.date)
        data = importer.fetch_date(target_date)
        if data:
            LiturgicalSyncService.import_verified_data(importer.session, data)
            importer.session.commit()
            print(f"Imported {target_date}")
        else:
            print(f"No data found for {target_date}")
    else:
        stats = importer.import_year(args.year)
        print(f"\nFinal statistics: {stats}")


if __name__ == "__main__":
    main()

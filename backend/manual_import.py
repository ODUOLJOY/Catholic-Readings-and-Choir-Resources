"""
Manual import of verified liturgical data.

This script allows importing structured reading references from a JSON file
or YAML file. It is designed for use when automatic fetching is unavailable.

The data must follow the schema:
{
  "date": "YYYY-MM-DD",
  "region": "KE",
  "celebration": "Celebration Name",
  "rank": "Solemnity|Feast|Memorial|Feria|Sunday",
  "liturgical_color": "White|Red|Green|Purple|Rose|Black",
  "sunday_cycle": "A|B|C",
  "weekday_cycle": "I|II",
  "season": "Advent|Christmas|Ordinary Time|Lent|Holy Week|Triduum|Easter",
  "week": 1-34,
  "source": "Source Name",
  "source_record_id": "external_identifier",
  "reading_sets": [
    {
      "type": "daily|proper|common|alternative",
      "selection_status": "weekday_default|strictly_proper|suggested|common_option",
      "celebration_name": "Optional celebration name",
      "lectionary_number": "123",
      "authority_level": "general_roman|national|diocesan|parish",
      "readings": [
        {
          "type": "FIRST_READING|RESPONSORIAL_PSALM|SECOND_READING|GOSPEL_ACCLAMATION|GOSPEL",
          "book": "Galatians",
          "chapter_start": 3,
          "verse_start": "22",
          "chapter_end": 3,
          "verse_end": "29",
          "display_reference": "Galatians 3:22-29",
          "psalm_number_variant": "105",
          "sequence": 0,
          "is_alternative": false,
          "is_optional": false,
          "is_primary": true,
          "lectionary_number": "123",
          "comment": "Optional comment"
        }
      ]
    }
  ]
}

Usage:
    python manual_import.py --file data.json
    python manual_import.py --file data.yaml --dry-run
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from sqlalchemy.orm import sessionmaker
from app.db.database import engine
from app.services.liturgical_sync import LiturgicalSyncService


def load_data_file(file_path: Path) -> Dict:
    """Load liturgical data from JSON or YAML file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    suffix = file_path.suffix.lower()
    
    if suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif suffix in [".yaml", ".yml"]:
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML files. Install with: pip install pyyaml")
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .json, .yaml, or .yml")


def validate_data(data: Dict) -> bool:
    """Validate that the data has required fields."""
    required_fields = ["date", "celebration", "rank", "liturgical_color"]
    
    for field in required_fields:
        if field not in data:
            print(f"Missing required field: {field}")
            return False
    
    # Validate date format
    try:
        date.fromisoformat(data["date"])
    except ValueError:
        print(f"Invalid date format: {data['date']}. Use YYYY-MM-DD")
        return False
    
    # Validate rank
    valid_ranks = ["Solemnity", "Feast", "Memorial", "Feria", "Sunday", "Commemoration"]
    if data["rank"] not in valid_ranks:
        print(f"Invalid rank: {data['rank']}. Valid ranks: {valid_ranks}")
        return False
    
    # Validate color
    valid_colors = ["White", "Red", "Green", "Purple", "Rose", "Black"]
    if data["liturgical_color"] not in valid_colors:
        print(f"Invalid color: {data['liturgical_color']}. Valid colors: {valid_colors}")
        return False
    
    return True


def import_single_record(
    data: Dict,
    session,
    dry_run: bool = False
) -> bool:
    """Import a single liturgical day record."""
    if not validate_data(data):
        return False
    
    if dry_run:
        print(f"[DRY RUN] Would import: {data['date']} - {data['celebration']}")
        return True
    
    try:
        LiturgicalSyncService.import_verified_data(session, data)
        session.commit()
        print(f"Imported: {data['date']} - {data['celebration']}")
        return True
    except Exception as e:
        print(f"Error importing {data['date']}: {e}")
        session.rollback()
        return False


def import_file(
    file_path: Path,
    dry_run: bool = False
) -> Dict:
    """Import liturgical data from a file."""
    session = sessionmaker(bind=engine)()
    
    try:
        data = load_data_file(file_path)
        
        # Check if data is a single record or a list
        if isinstance(data, list):
            records = data
        else:
            records = [data]
        
        stats = {
            "total": len(records),
            "imported": 0,
            "skipped": 0,
            "errors": 0,
        }
        
        for record in records:
            if import_single_record(record, session, dry_run):
                stats["imported"] += 1
            else:
                stats["errors"] += 1
        
        return stats
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Manual import of verified liturgical data")
    parser.add_argument("--file", "-f", required=True, help="Path to JSON or YAML file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without importing")
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    
    print(f"Loading data from: {file_path}")
    
    stats = import_file(file_path, dry_run=args.dry_run)
    
    print(f"\nImport statistics:")
    print(f"  Total records: {stats['total']}")
    print(f"  Imported: {stats['imported']}")
    print(f"  Errors: {stats['errors']}")
    
    if args.dry_run:
        print("\n[DRY RUN] No data was actually imported.")
    
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

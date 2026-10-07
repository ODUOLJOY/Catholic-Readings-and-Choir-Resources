"""Online lectionary source adapter.

Fetches the liturgical calendar + daily-reading *references* from the Universalis
public JSONP endpoint (https://universalis.com/{region}/{YYYYMMDD}/jsonp.js) and
shapes them for ``LiturgicalSyncService.import_verified_data``.

This stores REFERENCES (book / chapter / verse) and calendar metadata only —
never the text of the readings themselves, which is a separately-licensed
concern and is intentionally NOT fetched here. A network/HTTP failure returns
``None`` so callers can fall back to the offline calendar engine without
raising.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable, Dict, Optional

import requests

from app.services.universalis_parser import UniversalisParser

UNIVERSALIS_BASE = "https://universalis.com"

# (jsonp key, internal reading type) for the weekday reading slots.
_READING_SLOTS = (
    ("first_reading", "FIRST_READING"),
    ("psalm", "RESPONSORIAL_PSALM"),
    ("second_reading", "SECOND_READING"),
    ("gospel", "GOSPEL"),
)


def _parse_jsonp(text: str) -> dict:
    """Strip the ``callback(...)`` wrapper from a JSONP response."""
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end == -1:
        return {}
    return json.loads(text[start + 1 : end])


def fetch_jsonp(
    target_date: date,
    region: str = "KE",
    timeout: float = 30.0,
    http=requests,
) -> Optional[dict]:
    """Fetch raw Universalis JSONP for a date.

    Returns the parsed dict, or ``None`` on any network/HTTP/parse failure
    (including air-gapped/offline environments). ``http`` is injectable for
    testing.
    """
    url = f"{UNIVERSALIS_BASE}/{region}/{target_date.strftime('%Y%m%d')}/jsonp.js"
    try:
        resp = http.get(url, timeout=timeout)
        resp.raise_for_status()
        return _parse_jsonp(resp.text)
    except (requests.RequestException, ValueError):
        return None


def _parse_reading(reference: str, reading_type: str) -> Optional[Dict[str, Any]]:
    if not reference:
        return None
    parsed = UniversalisParser.parse_reference(reference)
    parsed["type"] = reading_type
    parsed["is_primary"] = True
    parsed["is_alternative"] = False
    parsed["is_optional"] = False
    parsed["sequence"] = 0
    return parsed


def _map_reading_type(universalis_type: str) -> str:
    return UniversalisParser.READING_TYPES.get(
        universalis_type,
        universalis_type.upper().replace(" ", "_"),
    )


def _parse_universalis_data(data: dict, target_date: date, region: str) -> dict:
    celebration = data.get("celebration", {}) or {}
    readings = data.get("readings", {}) or {}

    primary_set: Dict[str, Any] = {
        "type": "daily",
        "selection_status": "weekday_default",
        "readings": [],
    }
    for key, reading_type in _READING_SLOTS:
        if key in readings:
            ref = _parse_reading(readings[key], reading_type)
            if ref:
                primary_set["readings"].append(ref)

    reading_sets: list[Dict[str, Any]] = [primary_set]

    if "proper_readings" in data:
        proper_set: Dict[str, Any] = {
            "type": "proper",
            "selection_status": "strictly_proper",
            "celebration_name": celebration.get("name"),
            "readings": [],
        }
        for reading_type, reference in (data["proper_readings"] or {}).items():
            ref = _parse_reading(reference, _map_reading_type(reading_type))
            if ref:
                proper_set["readings"].append(ref)
        if proper_set["readings"]:
            reading_sets.append(proper_set)

    return {
        "date": target_date.isoformat(),
        "region": region,
        "celebration": celebration.get("name", "Weekday"),
        "rank": UniversalisParser.parse_celebration_rank(celebration.get("rank", "Feria")),
        "liturgical_color": celebration.get("color", "Green"),
        "sunday_cycle": data.get("sunday_cycle", "A"),
        "weekday_cycle": data.get("weekday_cycle", "I"),
        "season": data.get("season", "Ordinary Time"),
        "week": data.get("week"),
        "source": "Universalis",
        "source_record_id": f"{region}_{target_date.isoformat()}",
        "reading_sets": reading_sets,
    }


def build_payload(
    target_date: date,
    region: str = "KE",
    fetcher: Optional[Callable[..., Optional[dict]]] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch + parse a date into the ``import_verified_data`` payload shape.

    ``fetcher`` is injected for testing; it defaults to the real HTTP fetcher.
    Any exception from the fetcher is treated as "source unavailable" → ``None``.
    """
    fetch = fetcher or fetch_jsonp
    try:
        data = fetch(target_date, region=region)
    except Exception:
        return None
    if not data:
        return None
    return _parse_universalis_data(data, target_date, region)

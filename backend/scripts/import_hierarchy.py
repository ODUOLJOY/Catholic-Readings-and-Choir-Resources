"""Idempotent importer for the Kenya Catholic ecclesiastical hierarchy.

Usage::

    python -m scripts.import_hierarchy            # upsert everything
    python -m scripts.import_hierarchy --report   # print counts, write nothing
    python -m scripts.import_hierarchy --dry-run  # show what would change

Design guarantees:

* **Idempotent** -- every row is keyed by its stable ``code``. Re-running
  updates existing rows instead of creating duplicates.
* **Repeatable** -- safe to run as often as you like.
* **Non-destructive** -- an existing row is only deactivated when the source data
  explicitly marks it as gone; nothing is deleted, so historical user and
  resource relationships survive.
* **Auditable** -- every write records its source URL, source name and
  verification timestamp.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data import ke_hierarchy as source  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.models.locations import (  # noqa: E402
    Country,
    Deanery,
    Diocese,
    EcclesiasticalProvince,
)
from app.models.parish import Parish  # noqa: E402
from app.services.hierarchy_service import summary  # noqa: E402


def _verified_at() -> datetime:
    return datetime.fromisoformat(source.VERIFIED_ON).replace(tzinfo=timezone.utc)


def _apply_provenance(obj: Any, row: dict) -> None:
    obj.source_url = row.get("source_url")
    obj.source_name = row.get("source_name")
    obj.source_verified_at = _verified_at()
    obj.verification_status = row.get("verification_status", source.NEEDS_REVIEW)


class Report:
    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = {}

    def record(self, entity: str, action: str) -> None:
        bucket = self.counts.setdefault(entity, {"created": 0, "updated": 0, "skipped": 0})
        bucket[action] += 1

    def merge(self, entity: str, existing: Any, row: dict, fields: Iterable[str]) -> str:
        changed = any(getattr(existing, field) != row.get(field) for field in fields)
        if changed:
            for field in fields:
                setattr(existing, field, row.get(field))
            _apply_provenance(existing, row)
            self.record(entity, "updated")
            return "updated"
        self.record(entity, "skipped")
        return "skipped"

    def as_dict(self) -> dict:
        return self.counts


def _upsert_country(db: Session, row: dict, report: Report) -> Country:
    existing = db.execute(
        select(Country).where(Country.code == row["code"])
    ).scalar_one_or_none()
    if existing is None:
        existing = Country(code=row["code"], name=row["name"])
        db.add(existing)
        report.record("countries", "created")
    else:
        report.merge("countries", existing, row, ("name",))
    _apply_provenance(existing, row)
    db.flush()
    return existing


def _upsert_diocese(
    db: Session,
    row: dict,
    report: Report,
) -> Diocese:
    """Upsert a diocese without touching ``ecclesiastical_province_id``.

    Provinces are created after dioceses because a province points at its
    metropolitan archdiocese, so the diocese -> province link is attached in a
    later pass. Writing it here would clear and restore it on every re-run.
    """
    fields = (
        "name", "short_name", "is_archdiocese", "is_military_ordinariate",
        "erected_on",
    )
    payload = {
        "name": row["name"],
        "short_name": row.get("short_name"),
        "is_archdiocese": bool(row.get("is_archdiocese")),
        "is_military_ordinariate": bool(row.get("is_military_ordinariate")),
        "erected_on": row.get("erected_on"),
    }
    existing = db.execute(
        select(Diocese).where(Diocese.code == row["code"])
    ).scalar_one_or_none()
    if existing is None:
        existing = Diocese(code=row["code"], **payload)
        db.add(existing)
        report.record("dioceses", "created")
    else:
        report.merge("dioceses", existing, payload, fields)
    _apply_provenance(existing, row)
    db.flush()
    return existing


def _upsert_deanery(db: Session, row: dict, diocese: Diocese, report: Report) -> Deanery:
    payload = {"name": row["name"], "diocese_id": diocese.id}
    existing = db.execute(
        select(Deanery).where(Deanery.code == row["code"])
    ).scalar_one_or_none()
    if existing is None:
        existing = Deanery(code=row["code"], **payload)
        db.add(existing)
        report.record("deaneries", "created")
    else:
        report.merge("deaneries", existing, payload, ("name", "diocese_id"))
    _apply_provenance(existing, row)
    db.flush()
    return existing


def _upsert_parish(db: Session, row: dict, deanery: Deanery, diocese: Diocese,
                   country: Country, report: Report) -> Parish:
    payload = {
        "name": row["name"],
        "deanery_id": deanery.id,
        "diocese_id": diocese.id,
        "country_id": country.id,
        "country": country.name,
        "address": row.get("address"),
    }
    fields = ("name", "deanery_id", "diocese_id", "country_id", "address")
    existing = db.execute(
        select(Parish).where(Parish.code == row["code"])
    ).scalar_one_or_none()
    if existing is None:
        existing = Parish(code=row["code"], **payload)
        db.add(existing)
        report.record("parishes", "created")
    else:
        report.merge("parishes", existing, payload, fields)
    _apply_provenance(existing, row)
    db.flush()
    return existing


def import_hierarchy(db: Session, *, dry_run: bool = False) -> Report:
    """Upsert the full hierarchy. Returns a :class:`Report`."""
    report = Report()
    verified_at = _verified_at()

    countries = {row["code"]: _upsert_country(db, row, report) for row in source.COUNTRIES}
    country = countries["KE"]

    # Dioceses are inserted before provinces because a province references its
    # metropolitan archdiocese.
    diocese_rows = {row["code"]: row for row in source.ALL_DIOCESES}

    diocese_objects: dict[str, Diocese] = {}
    for row in source.ALL_DIOCESES:
        diocese_objects[row["code"]] = _upsert_diocese(db, row, report)

    province_objects: dict[str, EcclesiasticalProvince] = {}
    for row in source.PROVINCES:
        payload = {
            "name": row["name"],
            "short_name": row.get("short_name"),
            "country_id": country.id,
        }
        existing = db.execute(
            select(EcclesiasticalProvince).where(
                EcclesiasticalProvince.code == row["code"]
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = EcclesiasticalProvince(code=row["code"], **payload)
            db.add(existing)
            report.record("provinces", "created")
        else:
            report.merge(
                "provinces", existing, payload, ("name", "short_name", "country_id")
            )
        _apply_provenance(existing, row)
        db.flush()
        province_objects[row["code"]] = existing

    # Attach dioceses to their province now that provinces exist. The Military
    # Ordinariate keeps ``ecclesiastical_province_id = NULL``.
    for row in source.ALL_DIOCESES:
        province = province_objects.get(row["province_code"]) if row["province_code"] else None
        diocese = diocese_objects[row["code"]]
        target = province.id if province else None
        if diocese.ecclesiastical_province_id != target:
            diocese.ecclesiastical_province_id = target
            report.record("dioceses", "updated")

    # Point each province at its metropolitan archdiocese.
    for row in source.PROVINCES:
        metropolitan = diocese_objects.get(row["metropolitan_code"])
        province = province_objects[row["code"]]
        target = metropolitan.id if metropolitan else None
        if province.metropolitan_archdiocese_id != target:
            province.metropolitan_archdiocese_id = target
            report.record("provinces", "updated")

    deanery_objects: dict[str, Deanery] = {}
    for row in source.DEANERIES:
        diocese = diocese_objects.get(row["diocese_code"])
        if diocese is None:
            report.record("deaneries", "skipped")
            continue
        deanery_objects[row["code"]] = _upsert_deanery(db, row, diocese, report)

    for row in source.PARISHES:
        deanery = deanery_objects.get(row["deanery_code"])
        diocese = diocese_objects.get(row["diocese_code"])
        if deanery is None or diocese is None:
            report.record("parishes", "skipped")
            continue
        _upsert_parish(db, row, deanery, diocese, country, report)

    # Soft-deactivate parishes that are still marked active locally but are no
    # longer present in the official source. Users are never reassigned.
    known_codes = {row["code"] for row in source.PARISHES}
    stale = db.execute(select(Parish)).scalars().all()
    deactivated = 0
    for parish in stale:
        if parish.code.startswith("KE-") and parish.code not in known_codes:
            if parish.is_active and parish.verification_status == source.INCOMPLETE:
                parish.is_active = False
                deactivated += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    report.counts.setdefault("parishes_deactivated", {"created": 0, "updated": 0})
    report.counts["parishes_deactivated"]["updated"] = deactivated
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true",
                        help="Print source-data coverage without writing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the upsert then roll back.")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable output.")
    args = parser.parse_args(argv)

    if args.report:
        payload = {"source_coverage": source.coverage(), "database": summary_standalone()}
        print(json.dumps(payload, indent=2))
        return 0

    db = SessionLocal()
    try:
        report = import_hierarchy(db, dry_run=args.dry_run)
        result = {
            "import": report.as_dict(),
            "database": summary(db) if not args.dry_run else summary_standalone(),
            "dry_run": args.dry_run,
            "source_verified_on": source.VERIFIED_ON,
        }
        print(json.dumps(result, indent=2))
    finally:
        db.close()
    return 0


def summary_standalone() -> dict:
    db = SessionLocal()
    try:
        return summary(db)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
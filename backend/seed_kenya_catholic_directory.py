"""Seed the Kenyan Catholic Church hierarchy from the KCCB directory data.

This script reads from the authoritative ``app/data/ke_hierarchy.py`` module and
ensures the full cascade Country -> Ecclesiastical Province -> Diocese ->
Deanery -> Parish is present and internally consistent in the database.

It is idempotent: re-running it updates existing rows in place and skips rows
that are already correct.

Usage::

    python seed_kenya_catholic_directory.py
"""

import json
import sys
import os
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.locations import (
    Country,
    Deanery,
    Diocese,
    EcclesiasticalProvince,
    VerificationStatus,
)
from app.models.parish import Parish
from app.data.ke_hierarchy import (
    COUNTRIES,
    PROVINCES,
    ALL_DIOCESES,
    DEANERIES,
    PARISHES,
    KCCB_DIOCESES_URL,
    KCCB_ORG_URL,
    VERIFIED,
)


def _upsert_country(db: Session, data: dict) -> Country:
    row = db.query(Country).filter(Country.code == data["code"]).first()
    if row:
        for key in ("name", "is_active", "source_url", "source_name",
                     "verification_status"):
            if key in data:
                setattr(row, key, data[key])
        return row
    row = Country(
        name=data["name"],
        code=data["code"],
        source_url=data.get("source_url"),
        source_name=data.get("source_name"),
        verification_status=data.get("verification_status", VERIFIED),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    print(f"Added Country: {row.name}")
    return row


def _upsert_provinces(db: Session, country: Country) -> dict[str, EcclesiasticalProvince]:
    """Create provinces keyed by their stable code. Returns code -> row."""
    by_code: dict[str, EcclesiasticalProvince] = {}
    for meta in PROVINCES:
        row = db.query(EcclesiasticalProvince).filter_by(code=meta["code"]).first()
        if row:
            for key in ("name", "short_name", "country_id", "is_active",
                         "source_url", "source_name", "verification_status"):
                if key in meta or key == "country_id":
                    val = meta.get(key) if key in meta else country.id
                    if key == "country_id":
                        val = country.id
                    setattr(row, key, val)
        else:
            row = EcclesiasticalProvince(
                name=meta["name"],
                code=meta["code"],
                short_name=meta.get("short_name"),
                country_id=country.id,
                source_url=meta.get("source_url"),
                source_name=meta.get("source_name"),
                verification_status=meta.get("verification_status", VERIFIED),
            )
            db.add(row)
            db.refresh(row) if False else None
            print(f"Added Province: {row.name}")
        by_code[meta["code"]] = row
    db.commit()
    return by_code


def _upsert_dioceses(
    db: Session,
    provinces_by_code: dict[str, EcclesiasticalProvince],
) -> dict[str, Diocese]:
    """Create / update dioceses and link them to provinces. Returns code -> row."""
    by_code: dict[str, Diocese] = {}
    # Build a name -> province lookup for the legacy inline data path.
    for ddef in ALL_DIOCESES:
        code = ddef["code"]
        name = ddef["name"]
        row = db.query(Diocese).filter(Diocese.code == code).first()
        # Also try to find by name (old-style mnemonic codes may differ).
        if row is None:
            row = db.query(Diocese).filter(Diocese.name == name).first()
        province_code = ddef.get("province_code")
        province_id = provinces_by_code[province_code].id if province_code else None

        if row:
            row.name = name
            row.is_archdiocese = ddef.get("is_archdiocese", False)
            row.is_military_ordinariate = ddef.get("is_military_ordinariate", False)
            row.ecclesiastical_province_id = province_id
            if ddef.get("erected_on"):
                row.erected_on = ddef["erected_on"]
        else:
            row = Diocese(
                name=name,
                code=code,
                short_name=ddef.get("short_name"),
                ecclesiastical_province_id=province_id,
                is_archdiocese=ddef.get("is_archdiocese", False),
                is_military_ordinariate=ddef.get("is_military_ordinariate", False),
                erected_on=ddef.get("erected_on"),
                source_url=ddef.get("source_url"),
                source_name=ddef.get("source_name"),
                verification_status=ddef.get("verification_status", VERIFIED),
            )
            db.add(row)
            print(f"  Added Diocese: {name} (code={code})")
        by_code[code] = row
    db.commit()

    # Set metropolitan_archdiocese_id on each province (needs diocese ids).
    for meta in PROVINCES:
        metro_code = meta.get("metropolitan_code")
        if not metro_code:
            continue
        province = provinces_by_code[meta["code"]]
        metro = by_code.get(metro_code)
        if metro and province.metropolitan_archdiocese_id != metro.id:
            province.metropolitan_archdiocese_id = metro.id
    db.commit()
    return by_code


# ---------------------------------------------------------------------------
# Legacy reconciliation + parish seeding
# ---------------------------------------------------------------------------

# Pre-migration mnemonic codes that exist in the database but have been
# superseded by the stable-code data in ke_hierarchy.py. The importer migrates
# their content (parishes) to the canonical deanery and then removes them so the
# hierarchy only contains one record per real-world jurisdiction.
_LEGACY_DEANERY_REPLACEMENTS = {
    "d_nbo_central": "KE-NRB-NBI-NAIROBI-CENTRAL",  # "Central Deanery" -> "Nairobi Central Deanery"
}

# Legacy parish display names that must be canonicalised to the authoritative
# name in ke_hierarchy.py so the parish upsert merges instead of duplicates.
# Keyed by legacy deanery code -> {old_name: canonical_name}.
_PARISH_RENAMES = {
    "d_nbo_central": {
        "Holy Family Basilica": "Holy Family Minor Basilica Parish",
    },
}


def _reconcile_legacy_deaneries(
    db: Session, deaneries_by_code: dict[str, Deanery]
) -> None:
    """Re-parent parishes from pre-migration deaneries into their canonical
    successors and delete the legacy deanery rows.

    This keeps parish primary keys stable (so existing user -> parish links are
    not broken) while eliminating duplicate deanery entries that existed only
    because of the old mnemonic-code data model.
    """
    for legacy_code, canonical_code in _LEGACY_DEANERY_REPLACEMENTS.items():
        canonical = deaneries_by_code.get(canonical_code)
        legacy = db.query(Deanery).filter(Deanery.code == legacy_code).first()
        if legacy is None:
            # Already reconciled on a previous run.
            continue
        if canonical is None:
            print(
                f"  WARNING: legacy deanery '{legacy.name}' (code={legacy_code}) "
                f"found but canonical '{canonical_code}' not created — leaving as-is."
            )
            continue

        # Move every parish from the legacy deanery to the canonical one.
        moved = 0
        for parish in db.query(Parish).filter(Parish.deanery_id == legacy.id).all():
            # If a parish with the same name already exists under the canonical
            # deanery, merge the metadata instead of creating a duplicate.
            existing = (
                db.query(Parish)
                .filter(
                    Parish.deanery_id == canonical.id,
                    Parish.name == parish.name,
                )
                .first()
            )
            if existing is not None and existing.id != parish.id:
                # Update the existing parish with richer data, then remove the
                # legacy copy. This keeps a single stable id for users.
                for key in ("address", "source_url", "verification_status", "county", "town"):
                    val = getattr(parish, key)
                    if val is not None:
                        setattr(existing, key, val)
                db.delete(parish)
                print(
                    f"  Merged legacy parish '{parish.name}' (id={parish.id}) "
                    f"into '{existing.name}' (id={existing.id}) under {canonical.name}"
                )
            else:
                # Re-parent the legacy parish to the canonical deanery.
                parish.deanery_id = canonical.id
                # Canonicalise the parish name to match the authoritative data
                # set, so the subsequent upsert merges rather than duplicates.
                renames = _PARISH_RENAMES.get(legacy_code, {})
                if parish.name in renames:
                    parish.name = renames[parish.name]
                moved += 1
                print(
                    f"  Re-parented parish '{parish.name}' (id={parish.id}) "
                    f"-> {canonical.name}"
                )
        # Capture display fields before the bulk delete (which desynchronises
        # the in-memory object via synchronize_session=False).
        legacy_name = legacy.name

        db.query(Deanery).filter(Deanery.id == legacy.id).delete(
            synchronize_session=False
        )
        db.commit()
        print(
            f"  Removed legacy deanery '{legacy_name}' "
            f"(code={legacy_code}, id={legacy.id}); {moved} parish(es) re-parented."
        )


def _cleanup_orphan_legacy_parishes(db: Session) -> None:
    """Remove or canonicalise parish rows that still carry a pre-migration
    mnemonic code (e.g. ``p_nbo_hfb``) even though their legacy parent deanery
    has already been deleted by a previous run of ``_reconcile_legacy_deaneries``.

    On every run ``_reconcile_legacy_deaneries`` only acts when the legacy
    *deanery* row still exists.  If the deanery was already removed but the
    parish rename/merge was rolled back (which can happen when a later
    ``_upsert_parishes`` commit fails), the orphan parish lingers with its old
    code and old display name, while a *second* canonical parish may have been
    created underneath the same deanery — producing a duplicate.

    This function prevents that drift.  For every legacy-code parish it looks
    up the authoritative data in ``PARISHES`` and either:

    * **deletes** the orphan (when no user or other FK references it and a
      canonical parish for the same real-world church already exists), or
    * **re-points** the orphan to the canonical code / name / address (when it
      is the one referenced by users and the canonical one is free to be
      removed or merged).
    """
    from app.models.user import User as UserModel

    # Build a name -> canonical parish data lookup for quick resolution.
    canonical_by_name: dict[str, dict] = {}
    for pdef in PARISHES:
        canonical_by_name[pdef["name"]] = pdef

    legacy_rows = db.query(Parish).filter(
        ~Parish.code.like("KE-%")
    ).all()

    for legacy in legacy_rows:
        # Determine the canonical name via the rename map (if the legacy
        # parish was already renamed in a prior run) or the raw name.
        canonical_name = legacy.name
        for rename_map in _PARISH_RENAMES.values():
            if legacy.name in rename_map.values():
                canonical_name = legacy.name
                break
        if canonical_name not in canonical_by_name:
            # Also try the old name via the rename maps.
            for rename_map in _PARISH_RENAMES.values():
                if legacy.name in rename_map:
                    canonical_name = rename_map[legacy.name]
                    break

        pdef = canonical_by_name.get(canonical_name)
        if pdef is None:
            print(
                f"  Orphan parish id={legacy.id} (code={legacy.code}) "
                f"has no canonical match — leaving as-is."
            )
            continue

        # Does a canonical parish (by stable code) already exist?
        canonical_db = db.query(Parish).filter(
            Parish.code == pdef["code"]
        ).first()

        if canonical_db is not None and canonical_db.id != legacy.id:
            # Duplicate exists. Decide which to keep.
            user_count = db.query(UserModel).filter(
                UserModel.parish_id == legacy.id
            ).count()
            if user_count > 0:
                # Keep the legacy row (users reference it); update it with
                # canonical data and delete the duplicate.
                for key in ("code", "name", "address", "source_url",
                            "source_name", "verification_status", "country",
                            "country_id", "county", "town"):
                    val = getattr(canonical_db, key)
                    if val is not None:
                        setattr(legacy, key, val)
                db.delete(canonical_db)
                print(
                    f"  Kept legacy parish id={legacy.id} (referenced by "
                    f"{user_count} user(s)); deleted duplicate id="
                    f"{canonical_db.id} and adopted canonical data."
                )
            else:
                # No users reference the legacy row — delete it.
                db.delete(legacy)
                print(
                    f"  Deleted orphan legacy parish id={legacy.id} "
                    f"(code={legacy.code}); canonical id="
                    f"{canonical_db.id} retained."
                )
        else:
            # No canonical parish exists yet — adopt the canonical data.
            for key in ("code", "name", "address", "source_url",
                        "source_name", "verification_status", "country",
                        "country_id", "county", "town"):
                val = pdef.get(key)
                if val is not None:
                    setattr(legacy, key, val)
            print(
                f"  Canonised orphan parish id={legacy.id} "
                f"({legacy.code} -> {pdef['code']})"
            )
    db.commit()


def _upsert_parishes(
    db: Session, deaneries_by_code: dict[str, Deanery]
) -> None:
    """Create / update parishes from the authoritative PARISHES list.

    ``PARISHES`` is produced by :func:`ke_hierarchy.build_parishes` and each
    entry carries a stable ``code``, the canonical ``deanery_code`` it belongs
    to, and source / verification metadata. Parishes are matched to deaneries
    by stable code. Within a deanery, the unique constraint on
    ``(deanery_id, name)`` is respected by skipping rows whose parish name
    already exists under that deanery (these are left over from the legacy
    reconciliation above).
    """
    print("\nSeeding parishes...")
    added = 0
    updated = 0
    skipped = 0
    # Resolve the Kenya country row once so every parish inherits the
    # correct ``country`` / ``country_id`` (the DB column is NOT NULL even
    # though the ORM model declares it nullable).
    ke_country = db.query(Country).filter_by(code="KE").first()
    ke_country_id = ke_country.id if ke_country else None
    ke_country_name = ke_country.name if ke_country else "Kenya"

    for pdef in PARISHES:
        deanery = deaneries_by_code.get(pdef["deanery_code"])
        if deanery is None:
            print(
                f"  WARNING: deanery '{pdef['deanery_code']}' for parish "
                f"'{pdef['name']}' not found — skipping."
            )
            skipped += 1
            continue

        parish = db.query(Parish).filter(Parish.code == pdef["code"]).first()
        if parish is None:
            # Guard against a name collision with a re-parented legacy parish
            # that shares the canonical deanery.
            dup = (
                db.query(Parish)
                .filter(
                    Parish.deanery_id == deanery.id,
                    Parish.name == pdef["name"],
                )
                .first()
            )
            if dup is not None:
                # A parish with the same name already exists under this deanery
                # (e.g. the legacy "Holy Family Basilica" re-parented and
                # renamed to "Holy Family Minor Basilica Parish" in
                # reconciliation). Merge the canonical code and richer data
                # from ke_hierarchy.py into the existing record so there is only
                # one row per real-world parish.
                for key in ("code", "name", "address", "source_url",
                            "source_name", "verification_status"):
                    if key in pdef and pdef[key] is not None:
                        setattr(dup, key, pdef[key])
                if dup.diocese_id != deanery.diocese_id:
                    dup.diocese_id = deanery.diocese_id
                skipped += 1
                print(f"  Merged into existing '{pdef['name']}' (id={dup.id})")
                continue
            parish = Parish(
                name=pdef["name"],
                code=pdef["code"],
                deanery_id=deanery.id,
                diocese_id=deanery.diocese_id,
                country_id=ke_country_id,
                country=ke_country_name,
                address=pdef.get("address"),
                source_url=pdef.get("source_url"),
                source_name=pdef.get("source_name"),
                verification_status=pdef.get("verification_status", VERIFIED),
            )
            db.add(parish)
            added += 1
            print(f"  Added Parish: {pdef['name']} (deanery={deanery.name})")
        else:
            for key in ("name", "address", "source_url", "source_name",
                        "verification_status"):
                if key in pdef and pdef[key] is not None:
                    setattr(parish, key, pdef[key])
            if parish.diocese_id != deanery.diocese_id:
                parish.diocese_id = deanery.diocese_id
            if parish.deanery_id != deanery.id:
                parish.deanery_id = deanery.id
            updated += 1
    db.commit()
    print(f"  Parishes: {added} added, {updated} updated, {skipped} skipped.")


def seed():
    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # 1. Countries
        # ------------------------------------------------------------------
        print("Seeding countries...")
        country_by_code: dict[str, Country] = {}
        for c in COUNTRIES:
            country_by_code[c["code"]] = _upsert_country(db, c)

        # ------------------------------------------------------------------
        # 2. Ecclesiastical provinces
        # ------------------------------------------------------------------
        print("\nSeeding provinces...")
        ke_country = country_by_code.get("KE")
        if ke_country is None:
            # Fallback: find by name if the code didn't match.
            ke_country = db.query(Country).filter_by(code="KE").first()
        if ke_country is None:
            print("ERROR: Kenya (KE) country not found — cannot seed provinces.")
            return

        provinces_by_code = _upsert_provinces(db, ke_country)
        print(f"  {len(provinces_by_code)} provinces ensured.")

        # ------------------------------------------------------------------
        # 3. Dioceses (linked to provinces)
        # ------------------------------------------------------------------
        print("\nSeeding dioceses...")
        dioceses_by_code = _upsert_dioceses(db, provinces_by_code)

        # Build a comprehensive lookup: stable code -> Diocese, plus old-style
        # mnemonic codes -> Diocese, so deanery/parish import can resolve
        # regardless of which code style a data source uses.
        dioceses_by_any_code: dict[str, Diocese] = {}
        for stable_code, diocese in dioceses_by_code.items():
            dioceses_by_any_code[stable_code] = diocese
            dioceses_by_any_code[diocese.code] = diocese  # old mnemonic code

        # ------------------------------------------------------------------
        # 4. Deaneries and parishes (from the directory JSON if present,
        #    otherwise from the hard-coded DEANERIES list).
        # ------------------------------------------------------------------
        deaneries_by_code: dict[str, Deanery] = {}
        parishes_by_code: dict[str, Parish] = {}

        # Load from JSON if available (rich deanery+parish data).
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "kenya_directory.json")
        if os.path.exists(json_path):
            print("\nSeeding locations from JSON...")
            with open(json_path, "r") as f:
                directory_data = json.load(f)

            for diocese_code, diocese_data in directory_data.items():
                # Resolve by any code style (stable or legacy mnemonic).
                diocese = dioceses_by_any_code.get(diocese_code)
                if diocese is None:
                    from app.services.hierarchy_service import resolve_legacy_diocese
                    diocese = resolve_legacy_diocese(db, diocese_code)
                if diocese is None:
                    print(f"  Jurisdiction '{diocese_code}' not found — skipping.")
                    continue

                for deanery_code, deanery_data in diocese_data.get("deaneries", {}).items():
                    if deanery_code in _LEGACY_DEANERY_REPLACEMENTS:
                        print(
                            f"  Skipping legacy deanery '{deanery_code}' "
                            f"(replaced by stable-code data)."
                        )
                        continue
                    deanery = db.query(Deanery).filter(Deanery.code == deanery_code).first()
                    if not deanery:
                        deanery = Deanery(
                            name=deanery_data["name"],
                            code=deanery_code,
                            diocese_id=diocese.id,
                            source_url=deanery_data.get("source_url"),
                            verification_status=deanery_data.get(
                                "verification_status", VERIFIED
                            ),
                        )
                        db.add(deanery)
                        db.commit()
                        print(f"  Added Deanery: {deanery_data['name']}")
                    else:
                        deanery.diocese_id = diocese.id
                    deaneries_by_code[deanery_code] = deanery
                    db.commit()

                    for parish_data in deanery_data.get("parishes", []):
                        parish_code = parish_data["code"]
                        parish = db.query(Parish).filter(Parish.code == parish_code).first()
                        if not parish:
                            parish = Parish(
                                name=parish_data["name"],
                                code=parish_code,
                                deanery_id=deanery.id,
                                diocese_id=diocese.id,
                                town=parish_data.get("town"),
                                county=parish_data.get("county"),
                                address=parish_data.get("address"),
                                source_url=parish_data.get("source_url"),
                                verification_status=parish_data.get(
                                    "verification_status", VERIFIED
                                ),
                            )
                            db.add(parish)
                            db.commit()
                            print(f"    Added Parish: {parish_data['name']}")
                        parishes_by_code[parish_code] = parish
        else:
            print("kenya_directory.json not found, using built-in deanery list.")

        # Always ensure the hard-coded DEANERIES are present (fallback / new data).
        print("\nEnsuring built-in deaneries are present...")
        for ddef in DEANERIES:
            deanery = db.query(Deanery).filter_by(code=ddef["code"]).first()
            # Resolve the diocese by stable code OR old mnemonic code.
            diocese = dioceses_by_any_code.get(ddef["diocese_code"])
            if diocese is None:
                print(f"  WARNING: diocese '{ddef['diocese_code']}' for deanery "
                      f"'{ddef['name']}' not found — skipping.")
                continue
            if deanery is None:
                deanery = Deanery(
                    name=ddef["name"],
                    code=ddef["code"],
                    diocese_id=diocese.id,
                    source_url=ddef.get("source_url"),
                    verification_status=ddef.get("verification_status", VERIFIED),
                )
                db.add(deanery)
                db.commit()
                print(f"  Added Deanery: {ddef['name']}")
            else:
                deanery.diocese_id = diocese.id
            deaneries_by_code[ddef["code"]] = deanery
        db.commit()

        # ------------------------------------------------------------------
        # 5. Reconcile legacy deaneries (pre-migration mnemonic codes) into
        #    their canonical stable-code successors, then seed parishes.
        # ------------------------------------------------------------------
        _reconcile_legacy_deaneries(db, deaneries_by_code)
        _cleanup_orphan_legacy_parishes(db)
        _upsert_parishes(db, deaneries_by_code)

        # Summary
        print("\n=== Seeding Summary ===")
        n_provinces = db.query(EcclesiasticalProvince).count()
        n_dioceses = db.query(Diocese).count()
        n_deaneries = db.query(Deanery).count()
        n_parishes = db.query(Parish).count()
        print(f"  Countries:   {db.query(Country).count()}")
        print(f"  Provinces:   {n_provinces}")
        print(f"  Dioceses:    {n_dioceses}")
        print(f"  Deaneries:   {n_deaneries}")
        print(f"  Parishes:    {n_parishes}")
        for p in db.query(EcclesiasticalProvince).all():
            dio_count = db.query(Diocese).filter_by(ecclesiastical_province_id=p.id).count()
            print(f"    {p.name}: {dio_count} dioceses")

    finally:
        db.close()
    print("\nSeeding complete.")


if __name__ == "__main__":
    seed()

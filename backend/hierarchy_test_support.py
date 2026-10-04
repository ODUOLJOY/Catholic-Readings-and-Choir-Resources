"""Shared builders for tests that need a valid ecclesiastical hierarchy.

The hierarchy is ``country -> province -> diocese -> deanery -> parish``. Because
``Parish.deanery_id`` and ``Parish.diocese_id`` are NOT NULL and the resolver
rejects a parish whose diocese disagrees with its deanery, tests must build a
complete chain rather than a bare diocese.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.locations import Country, Deanery, Diocese, EcclesiasticalProvince
from app.models.parish import Parish


def build_chain(
    db: Session,
    *,
    country_code: str = "KE",
    province_code: str = "KE-NRB",
    province_name: str = "Ecclesiastical Province of Nairobi",
    diocese_code: str = "KE-NRB-NBI",
    diocese_name: str = "Archdiocese of Nairobi",
    deanery_code: str = "KE-NRB-NBI-CENTRAL",
    deanery_name: str = "Nairobi Central Deanery",
    parish_code: str = "KE-NRB-NBI-CENTRAL-HOLY-FAMILY",
    parish_name: str = "Holy Family Minor Basilica Parish",
    metropolitan: bool = True,
):
    """Create and return a complete, consistent hierarchy chain."""
    country = Country(name="Kenya", code=country_code)
    db.add(country)
    db.flush()

    diocese = Diocese(
        name=diocese_name,
        code=diocese_code,
        short_name=diocese_name.replace("Archdiocese of ", "")
                              .replace("Diocese of ", ""),
        is_archdiocese=metropolitan,
    )
    db.add(diocese)
    db.flush()

    province = EcclesiasticalProvince(
        name=province_name,
        code=province_code,
        short_name=province_name.replace("Ecclesiastical Province of ", ""),
        country_id=country.id,
        metropolitan_archdiocese_id=diocese.id,
    )
    db.add(province)
    db.flush()

    diocese.ecclesiastical_province_id = province.id

    deanery = Deanery(name=deanery_name, code=deanery_code, diocese_id=diocese.id)
    db.add(deanery)
    db.flush()

    parish = Parish(
        name=parish_name,
        code=parish_code,
        deanery_id=deanery.id,
        diocese_id=diocese.id,
        country_id=country.id,
        country=country.name,
    )
    db.add(parish)
    db.commit()

    return {
        "country": country,
        "province": province,
        "diocese": diocese,
        "deanery": deanery,
        "parish": parish,
    }


def build_second_province_chain(
    db: Session,
    *,
    province_code: str = "KE-MBA",
    province_name: str = "Ecclesiastical Province of Mombasa",
    diocese_code: str = "KE-MBA-MBA",
    diocese_name: str = "Archdiocese of Mombasa",
    deanery_code: str = "KE-MBA-MBA-CENTRAL",
    deanery_name: str = "Central Deanery",
    parish_code: str = "KE-MBA-MBA-CENTRAL-TEST",
    parish_name: str = "Test Mombasa Parish",
):
    """A second chain in a different ecclesiastical province, for negative tests."""
    country = db.query(Country).filter(Country.code == "KE").first()
    if country is None:
        country = Country(name="Kenya", code="KE")
        db.add(country)
        db.flush()

    diocese = Diocese(
        name=diocese_name, code=diocese_code, short_name="Mombasa",
        is_archdiocese=True,
    )
    db.add(diocese)
    db.flush()

    province = EcclesiasticalProvince(
        name=province_name,
        code=province_code,
        short_name="Mombasa",
        country_id=country.id,
        metropolitan_archdiocese_id=diocese.id,
    )
    db.add(province)
    db.flush()

    diocese.ecclesiastical_province_id = province.id

    deanery = Deanery(name=deanery_name, code=deanery_code, diocese_id=diocese.id)
    db.add(deanery)
    db.flush()

    parish = Parish(
        name=parish_name,
        code=parish_code,
        deanery_id=deanery.id,
        diocese_id=diocese.id,
        country_id=country.id,
        country=country.name,
    )
    db.add(parish)
    db.commit()

    return {
        "country": country,
        "province": province,
        "diocese": diocese,
        "deanery": deanery,
        "parish": parish,
    }


__all__ = ["build_chain", "build_second_province_chain"]
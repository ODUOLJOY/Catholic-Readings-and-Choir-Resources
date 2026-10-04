"""Resolution and validation for the Kenya ecclesiastical hierarchy.

The hierarchy is::

    Country
      -> EcclesiasticalProvince (metropolitan province)
        -> Diocese / Archdiocese
          -> Deanery
            -> Parish
              -> User

Two rules are enforced everywhere in this module:

1. Clients never supply a chain of hierarchy ids. They supply the *leaf*
   (``parish_id``) and the ancestors are derived from the database.
2. Any denormalised ancestor is checked against its parent, so a parish can
   never claim a diocese that does not contain its deanery.

The Military Ordinariate is deliberately excluded from the geographic cascade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.locations import (
    Country,
    Deanery,
    Diocese,
    EcclesiasticalProvince,
    VerificationStatus,
)
from app.models.parish import Parish

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class HierarchyError(ValueError):
    """Raised when a hierarchy request is invalid or internally inconsistent."""


@dataclass(frozen=True)
class ResolvedParish:
    """A parish together with its full, verified ancestry."""

    parish: Parish
    deanery: Deanery
    diocese: Diocese
    province: EcclesiasticalProvince
    country: Country

    def as_dict(self) -> dict:
        return {
            "parish": {"id": self.parish.id, "name": self.parish.name,
                       "code": self.parish.code, "is_active": self.parish.is_active,
                       "verification_status": self.parish.verification_status},
            "deanery": {"id": self.deanery.id, "name": self.deanery.name,
                        "code": self.deanery.code},
            "diocese": {"id": self.diocese.id, "name": self.diocese.name,
                        "code": self.diocese.code,
                        "is_archdiocese": self.diocese.is_archdiocese},
            "province": {"id": self.province.id, "name": self.province.name,
                         "code": self.province.code,
                         "short_name": self.province.short_name},
            "country": {"id": self.country.id, "name": self.country.name,
                        "code": self.country.code},
        }


def _paginate(limit: Optional[int], offset: Optional[int]) -> tuple[int, int]:
    size = DEFAULT_PAGE_SIZE if limit is None else int(limit)
    if size < 1:
        raise HierarchyError("limit must be at least 1.")
    size = min(size, MAX_PAGE_SIZE)
    start = 0 if offset is None else int(offset)
    if start < 0:
        raise HierarchyError("offset must not be negative.")
    return size, start


def _paginated(
    db: Session,
    model,
    *,
    filters: dict,
    search_columns: tuple[str, ...],
    search: Optional[str],
    order_by,
    limit: Optional[int],
    offset: Optional[int],
) -> tuple[list, int]:
    size, start = _paginate(limit, offset)

    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    # ``filters`` is keyed by attribute name, so resolve each one to the real
    # column. Comparing the bare string instead would silently build
    # ``where(False)`` and every listing would come back empty.
    for name, value in filters.items():
        column = getattr(model, name)
        stmt = stmt.where(column == value)
        count_stmt = count_stmt.where(column == value)

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        clauses = [getattr(model, column).ilike(pattern) for column in search_columns]
        clause = or_(*clauses)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    # ``order_by`` must be a real column expression: SQLAlchemy 2.x cannot
    # resolve a bare string label such as "Parish.name" in ORDER BY.
    stmt = stmt.order_by(order_by, model.id).limit(size).offset(start)
    rows = list(db.execute(stmt).scalars().all())
    total = int(db.execute(count_stmt).scalar_one())
    return rows, total


# ---------------------------------------------------------------------------
# Public listing helpers
# ---------------------------------------------------------------------------

def list_countries(db: Session, *, search=None, limit=None, offset=None):
    return _paginated(
        db, Country,
        filters={"is_active": True},
        search_columns=("name", "code"),
        search=search, order_by=Country.name, limit=limit, offset=offset,
    )


def list_provinces(db: Session, *, country_id: int, search=None, limit=None, offset=None):
    country = db.get(Country, country_id)
    if country is None:
        raise HierarchyError(f"Country {country_id} not found.")
    return _paginated(
        db, EcclesiasticalProvince,
        filters={"country_id": country_id, "is_active": True},
        search_columns=("name", "code", "short_name"),
        search=search, order_by=EcclesiasticalProvince.name, limit=limit, offset=offset,
    )


def list_dioceses(db: Session, *, province_id: Optional[int] = None, search=None,
                 limit=None, offset=None, include_ordinariate: bool = False):
    """List dioceses.

    ``province_id`` narrows the result to one ecclesiastical province. Omit it to
    list every jurisdiction, which is also how the Military Ordinariate is
    reached: it is a separate jurisdiction with no province of its own, so it is
    only ever returned when ``include_ordinariate`` is set.
    """
    filters: dict = {"is_active": True}
    if province_id is not None:
        province = db.get(EcclesiasticalProvince, province_id)
        if province is None:
            raise HierarchyError(
                f"Ecclesiastical province {province_id} not found."
            )
        filters["ecclesiastical_province_id"] = province_id
    if not include_ordinariate:
        filters["is_military_ordinariate"] = False
    return _paginated(
        db, Diocese,
        filters=filters,
        search_columns=("name", "code", "short_name"),
        search=search, order_by=Diocese.name, limit=limit, offset=offset,
    )


# Directory payloads produced before the hierarchy migration identify
# jurisdictions with short mnemonics instead of stable codes. Only mnemonics that
# can be tied to a specific diocese by evidence in this repository are listed.
#
#   arch_nbo  kenya_directory.json stores the Archdiocese of Nairobi under this
#             key; locations.py documents it as a legacy jurisdiction identifier.
#   dio_kti   named alongside arch_nbo in the locations.py legacy-import comment
#             and corresponds to the Diocese of Kitui.
#   mil_ord   named in the same comment and corresponds to the Military
#             Ordinariate, which has no province or deanery cascade.
#
# Nothing else is included. The remaining historic mnemonics are not recorded
# anywhere in the repository, and inferring them from a diocese name would risk
# attaching directory data to the wrong diocese, so unknown identifiers resolve to
# ``None`` and are reported to the caller instead.
LEGACY_DIOCESE_CODE_ALIASES = {
    "arch_nbo": "KE-NRB-NBI",
    "dio_kti": "KE-NRB-KTI",
    "mil_ord": "KE-MIL-ORD",
}


def resolve_legacy_diocese(db: Session, code_or_name: str) -> Optional[Diocese]:
    """Find a diocese from an old-style identifier.

    Directory payloads produced before the hierarchy migration identify
    jurisdictions with codes such as ``arch_nbo`` / ``dio_kti`` / ``mil_ord``,
    or sometimes only with a display name such as ``Archdiocese of Nairobi``.
    Current rows use stable codes such as ``KE-NRB-NBI``.

    Resolution is attempted in order: exact current code, an explicit legacy alias
    from :data:`LEGACY_DIOCESE_CODE_ALIASES`, then a normalised display name.
    Nothing is guessed -- an ambiguous or unknown identifier returns ``None`` so
    the caller can report it instead of attaching data to the wrong diocese.
    """
    identifier = (code_or_name or "").strip()
    if not identifier:
        return None

    exact = db.execute(
        select(Diocese).where(Diocese.code == identifier)
    ).scalar_one_or_none()
    if exact is not None:
        return exact

    # A legacy mnemonic is translated to the current stable code and then looked
    # up exactly. If the diocese is absent, resolution falls through to the name
    # match below rather than guessing.
    aliased_code = LEGACY_DIOCESE_CODE_ALIASES.get(identifier.casefold())
    if aliased_code is not None:
        aliased = db.execute(
            select(Diocese).where(Diocese.code == aliased_code)
        ).scalar_one_or_none()
        if aliased is not None:
            return aliased

    target = _normalise_jurisdiction_name(identifier)
    if not target:
        return None

    matches = [
        row
        for row in db.execute(select(Diocese)).scalars()
        if _normalise_jurisdiction_name(row.name) == target
        or (
            row.short_name is not None
            and _normalise_jurisdiction_name(row.short_name) == target
        )
    ]
    if len(matches) != 1:
        # Zero matches means unknown; more than one means ambiguous. Both are
        # refused rather than resolved arbitrarily.
        return None
    return matches[0]


def _normalise_jurisdiction_name(value: str) -> str:
    """Reduce a jurisdiction label to a comparable token.

    ``Archdiocese of Nairobi``, ``archdiocese of nairobi`` and ``Nairobi`` all
    collapse to ``nairobi``, so legacy name-only payloads still resolve.

    Only a leading archdiocese/diocese qualifier is removed. Individual words
    are never dropped, because the Military Ordinariate has no other word and
    stripping "military" and "ordinariate" would leave it with an empty token.
    """
    text = (value or "").casefold().strip()
    for prefix in (
        "archdiocese of ",
        "diocese of ",
        "military ordinariate of ",
        "the archdiocese of ",
        "the diocese of ",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return "".join(ch for ch in text if ch.isalnum())


def list_deaneries(db: Session, *, diocese_id: int, search=None, limit=None, offset=None,
                   include_inactive: bool = False):
    diocese = db.get(Diocese, diocese_id)
    if diocese is None:
        raise HierarchyError(f"Diocese {diocese_id} not found.")
    filters = {"diocese_id": diocese_id}
    if not include_inactive:
        filters["is_active"] = True
    return _paginated(
        db, Deanery,
        filters=filters,
        search_columns=("name", "code"),
        search=search, order_by=Deanery.name, limit=limit, offset=offset,
    )


def list_parishes(db: Session, *, deanery_id: int, search=None, limit=None, offset=None,
                  include_inactive: bool = False):
    deanery = db.get(Deanery, deanery_id)
    if deanery is None:
        raise HierarchyError(f"Deanery {deanery_id} not found.")
    filters = {"deanery_id": deanery_id}
    if not include_inactive:
        filters["is_active"] = True
    return _paginated(
        db, Parish,
        filters=filters,
        search_columns=("name", "code", "town", "county"),
        search=search, order_by=Parish.name, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# Resolution / validation
# ---------------------------------------------------------------------------

def resolve_parish(
    db: Session,
    parish: Parish,
    *,
    require_active: bool = True,
) -> ResolvedParish:
    """Load and validate a parish's full ancestry.

    Raises :class:`HierarchyError` if the chain is missing or inconsistent.
    """
    if parish is None:
        raise HierarchyError("Parish not found.")
    if require_active and not parish.is_active:
        raise HierarchyError(
            f"Parish '{parish.name}' is not currently active. "
            "Please contact your parish administrator."
        )

    if parish.deanery_id is None:
        raise HierarchyError(f"Parish '{parish.name}' is not assigned to a deanery.")
    deanery = db.get(Deanery, parish.deanery_id)
    if deanery is None:
        raise HierarchyError(f"Deanery {parish.deanery_id} not found for '{parish.name}'.")
    if require_active and not deanery.is_active:
        raise HierarchyError(f"Deanery '{deanery.name}' is not currently active.")

    # The parish also carries a denormalised diocese_id. It must agree with the
    # deanery, otherwise the record is corrupt.
    if parish.diocese_id is None:
        raise HierarchyError(f"Parish '{parish.name}' is not assigned to a diocese.")
    if parish.diocese_id != deanery.diocese_id:
        diocese = db.get(Diocese, parish.diocese_id)
        raise HierarchyError(
            f"Parish '{parish.name}' is inconsistent: deanery '{deanery.name}' "
            f"belongs to a different diocese than "
            f"'{diocese.name if diocese else parish.diocese_id}'."
        )

    diocese = db.get(Diocese, parish.diocese_id)
    if diocese is None:
        raise HierarchyError(f"Diocese {parish.diocese_id} not found for '{parish.name}'.")
    if require_active and not diocese.is_active:
        raise HierarchyError(f"Diocese '{diocese.name}' is not currently active.")
    if diocese.is_military_ordinariate:
        raise HierarchyError(
            "The Military Ordinariate does not follow the "
            "province -> diocese -> deanery -> parish hierarchy."
        )

    if diocese.ecclesiastical_province_id is None:
        raise HierarchyError(
            f"Diocese '{diocese.name}' is not assigned to an ecclesiastical province."
        )
    province = db.get(EcclesiasticalProvince, diocese.ecclesiastical_province_id)
    if province is None:
        raise HierarchyError(
            f"Ecclesiastical province {diocese.ecclesiastical_province_id} not found "
            f"for '{diocese.name}'."
        )
    if require_active and not province.is_active:
        raise HierarchyError(f"Ecclesiastical province '{province.name}' is not active.")

    country = db.get(Country, province.country_id)
    if country is None:
        raise HierarchyError(f"Country {province.country_id} not found.")

    return ResolvedParish(
        parish=parish,
        deanery=deanery,
        diocese=diocese,
        province=province,
        country=country,
    )


def resolve_parish_by_id(db: Session, parish_id: int, *, require_active: bool = True
                         ) -> ResolvedParish:
    return resolve_parish(db, db.get(Parish, parish_id), require_active=require_active)


def resolve_user_hierarchy(db: Session, user) -> Optional[ResolvedParish]:
    """Return ``user``'s hierarchy, or ``None`` when no parish is assigned."""
    if user is None or user.parish_id is None:
        return None
    parish = db.get(Parish, user.parish_id)
    if parish is None:
        return None
    try:
        return resolve_parish(db, parish, require_active=False)
    except HierarchyError:
        return None


def validate_chain(
    db: Session,
    *,
    country_id: int,
    province_id: int,
    diocese_id: int,
    deanery_id: int,
    parish_id: Optional[int] = None,
) -> ResolvedParish:
    """Assert that every supplied id sits on one consistent chain.

    Used by the admin endpoints, which legitimately accept the whole chain.
    """
    country = db.get(Country, country_id)
    if country is None:
        raise HierarchyError("Country not found.")

    province = db.get(EcclesiasticalProvince, province_id)
    if province is None:
        raise HierarchyError("Ecclesiastical province not found.")
    if province.country_id != country_id:
        raise HierarchyError(
            f"Ecclesiastical province '{province.name}' does not belong to "
            f"'{country.name}'."
        )

    diocese = db.get(Diocese, diocese_id)
    if diocese is None:
        raise HierarchyError("Diocese not found.")
    if diocese.is_military_ordinariate:
        raise HierarchyError(
            "The Military Ordinariate cannot be part of a deanery or parish chain."
        )
    if diocese.ecclesiastical_province_id != province_id:
        raise HierarchyError(
            f"'{diocese.name}' does not belong to {province.name}."
        )

    deanery = db.get(Deanery, deanery_id)
    if deanery is None:
        raise HierarchyError("Deanery not found.")
    if deanery.diocese_id != diocese_id:
        raise HierarchyError(
            f"Deanery '{deanery.name}' does not belong to '{diocese.name}'."
        )

    if parish_id is None:
        raise HierarchyError("Parish not found.")
    parish = db.get(Parish, parish_id)
    if parish is None:
        raise HierarchyError("Parish not found.")
    if parish.deanery_id != deanery_id:
        raise HierarchyError(
            f"Parish '{parish.name}' does not belong to deanery '{deanery.name}'."
        )
    if parish.diocese_id != diocese_id:
        raise HierarchyError(
            f"Parish '{parish.name}' does not belong to diocese '{diocese.name}'."
        )

    return ResolvedParish(
        parish=parish,
        deanery=deanery,
        diocese=diocese,
        province=province,
        country=country,
    )


def summary(db: Session) -> dict:
    """Counts and verification coverage, used by the admin area and importer."""
    def count(model, *conditions):
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return int(db.execute(stmt).scalar_one())

    def by_status(model):
        rows = db.execute(
            select(model.verification_status, func.count()).group_by(
                model.verification_status
            )
        ).all()
        return {status: int(total) for status, total in rows}

    return {
        "countries": count(Country),
        "provinces": count(EcclesiasticalProvince),
        "dioceses": count(Diocese),
        "archdioceses": count(Diocese, Diocese.is_archdiocese.is_(True)),
        "military_ordinariates": count(
            Diocese, Diocese.is_military_ordinariate.is_(True)
        ),
        "dioceses_without_province": count(
            Diocese, Diocese.ecclesiastical_province_id.is_(None)
        ),
        "deaneries": count(Deanery),
        "parishes": count(Parish),
        "inactive_parishes": count(Parish, Parish.is_active.is_(False)),
        "verification_status": {
            "provinces": by_status(EcclesiasticalProvince),
            "dioceses": by_status(Diocese),
            "deaneries": by_status(Deanery),
            "parishes": by_status(Parish),
        },
        "allowed_verification_statuses": list(VerificationStatus.ALL),
    }


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "HierarchyError",
    "LEGACY_DIOCESE_CODE_ALIASES",
    "MAX_PAGE_SIZE",
    "ResolvedParish",
    "list_countries",
    "list_deaneries",
    "list_dioceses",
    "list_parishes",
    "list_provinces",
    "resolve_legacy_diocese",
    "resolve_parish",
    "resolve_parish_by_id",
    "resolve_user_hierarchy",
    "summary",
    "validate_chain",
]
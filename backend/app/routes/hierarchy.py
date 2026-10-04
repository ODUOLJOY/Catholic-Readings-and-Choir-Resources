"""Public, read-only hierarchy API.

The endpoints return **only children of the selected parent**, so a client can
never be handed a diocese from the wrong province or a parish from the wrong
deanery.

Routes::

    GET /api/v1/hierarchy/countries
    GET /api/v1/hierarchy/provinces?country_id=
    GET /api/v1/hierarchy/dioceses?province_id=
    GET /api/v1/hierarchy/deaneries?diocese_id=
    GET /api/v1/hierarchy/parishes?deanery_id=
    GET /api/v1/hierarchy/parishes/{parish_id}
    GET /api/v1/hierarchy/resolve?parish_id=
    GET /api/v1/hierarchy/summary          (admin)

These are public read endpoints because the signup screen must be able to
populate its selectors before the visitor has an account. They expose no user
data and reveal nothing that is not already published by the Church.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_optional_user
from app.routes.admin import require_admin
from app.services import hierarchy_service as svc

router = APIRouter(prefix="/api/v1/hierarchy", tags=["Hierarchy"])


def _fail(exc: svc.HierarchyError, code: int = status.HTTP_400_BAD_REQUEST):
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _envelope(items, total: int, limit: int, offset: int) -> dict:
    return {
        "count": len(items),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
        "results": items,
    }


def _page(limit: Optional[int], offset: Optional[int]) -> tuple[int, int]:
    size = svc.DEFAULT_PAGE_SIZE if limit is None else limit
    start = 0 if offset is None else offset
    return min(size, svc.MAX_PAGE_SIZE), start


@router.get("/countries")
def get_countries(
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        rows, total = svc.list_countries(db, search=search, limit=limit, offset=offset)
    except svc.HierarchyError as exc:
        _fail(exc)
    effective_limit, effective_offset = _page(limit, offset)
    return _envelope(
        [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "is_active": c.is_active,
                "verification_status": c.verification_status,
                "source_url": c.source_url,
            }
            for c in rows
        ],
        total, effective_limit, effective_offset,
    )


@router.get("/provinces")
def get_provinces(
    country_id: int = Query(..., description="Country id."),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        rows, total = svc.list_provinces(
            db, country_id=country_id, search=search, limit=limit, offset=offset
        )
    except svc.HierarchyError as exc:
        _fail(exc, status.HTTP_404_NOT_FOUND)
    effective_limit, effective_offset = _page(limit, offset)
    return _envelope(
        [
            {
                "id": p.id,
                "name": p.name,
                "short_name": p.short_name,
                "code": p.code,
                "metropolitan_archdiocese_id": p.metropolitan_archdiocese_id,
                "verification_status": p.verification_status,
                "source_url": p.source_url,
            }
            for p in rows
        ],
        total, effective_limit, effective_offset,
    )


@router.get("/dioceses")
def get_dioceses(
    province_id: Optional[int] = Query(
        None,
        description="Ecclesiastical province id. Omit to list every jurisdiction.",
    ),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
    include_ordinariate: bool = Query(
        False,
        description="Include the Military Ordinariate, which has no province.",
    ),
    db: Session = Depends(get_db),
):
    try:
        rows, total = svc.list_dioceses(
            db,
            province_id=province_id,
            search=search,
            limit=limit,
            offset=offset,
            include_ordinariate=include_ordinariate,
        )
    except svc.HierarchyError as exc:
        _fail(exc, status.HTTP_404_NOT_FOUND)
    effective_limit, effective_offset = _page(limit, offset)
    return _envelope(
        [
            {
                "id": d.id,
                "name": d.name,
                "short_name": d.short_name,
                "code": d.code,
                "is_archdiocese": d.is_archdiocese,
                "is_military_ordinariate": d.is_military_ordinariate,
                "erected_on": d.erected_on,
                "deanery_count": len(d.deaneries),
                "verification_status": d.verification_status,
                "source_url": d.source_url,
                "website": _website(d),
            }
            for d in rows
        ],
        total, effective_limit, effective_offset,
    )


def _website(diocese) -> Optional[str]:
    """Official diocesan website, recorded in the diocese source URL by the importer."""
    if diocese.source_url and diocese.source_url != "https://kccb.or.ke/dioceses/":
        return diocese.source_url
    return None


@router.get("/deaneries")
def get_deaneries(
    diocese_id: int = Query(..., description="Diocese id."),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if include_inactive:
        require_admin(current_user)
    try:
        rows, total = svc.list_deaneries(
            db,
            diocese_id=diocese_id,
            search=search,
            limit=limit,
            offset=offset,
            include_inactive=include_inactive,
        )
    except svc.HierarchyError as exc:
        _fail(exc, status.HTTP_404_NOT_FOUND)
    effective_limit, effective_offset = _page(limit, offset)
    return _envelope(
        [
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "diocese_id": d.diocese_id,
                "is_active": d.is_active,
                "parish_count": len(d.parishes),
                "verification_status": d.verification_status,
                "source_url": d.source_url,
            }
            for d in rows
        ],
        total, effective_limit, effective_offset,
    )


@router.get("/parishes")
def get_parishes(
    deanery_id: int = Query(..., description="Deanery id."),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if include_inactive:
        require_admin(current_user)
    try:
        rows, total = svc.list_parishes(
            db,
            deanery_id=deanery_id,
            search=search,
            limit=limit,
            offset=offset,
            include_inactive=include_inactive,
        )
    except svc.HierarchyError as exc:
        _fail(exc, status.HTTP_404_NOT_FOUND)
    effective_limit, effective_offset = _page(limit, offset)
    return _envelope(
        [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "deanery_id": p.deanery_id,
                "diocese_id": p.diocese_id,
                "town": p.town,
                "county": p.county,
                "address": p.address,
                "is_active": p.is_active,
                "verification_status": p.verification_status,
                "source_url": p.source_url,
            }
            for p in rows
        ],
        total, effective_limit, effective_offset,
    )


@router.get("/parishes/{parish_id}")
def get_parish_chain(
    parish_id: int,
    db: Session = Depends(get_db),
):
    """Full country -> province -> diocese -> deanery -> parish chain for one parish."""
    try:
        resolved = svc.resolve_parish_by_id(db, parish_id, require_active=False)
    except svc.HierarchyError as exc:
        _fail(exc, status.HTTP_404_NOT_FOUND)
    return resolved.as_dict()


@router.get("/resolve")
def resolve(
    parish_id: int = Query(..., description="Parish id selected during signup."),
    db: Session = Depends(get_db),
):
    """Validate a registration selection before submitting the form.

    Returns 200 with the derived chain when the parish is selectable, or 400 with
    a clear message when it is not (unknown, inactive or inconsistent).
    """
    try:
        resolved = svc.resolve_parish_by_id(db, parish_id, require_active=True)
    except svc.HierarchyError as exc:
        _fail(exc)
    return resolved.as_dict()


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    require_admin(current_user)
    return svc.summary(db)


__all__ = ["router"]
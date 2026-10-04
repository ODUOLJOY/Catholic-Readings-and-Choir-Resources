from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.calendar import get_calendar_info
from app.services.hierarchy_liturgy import get_liturgical_info_for_user
from app.routes.admin import require_admin
from app.routes.auth_dependency import get_current_user
from app.models.user import User
from app.models.liturgical import LiturgicalDay
from app.models.reading_reference import ReadingSet, ReadingReference
from app.services.liturgical_sync import LiturgicalSyncService

router = APIRouter(prefix="/api/v1/liturgy", tags=["Liturgy"])


@router.get("/today")
def get_today_liturgy(
    region: str = Query("KE"),
    db: Session = Depends(get_db),
):
    """Get liturgical information and reading references for today."""
    return get_liturgy_by_date(date.today(), region, db)


@router.get("/my/today")
def get_my_today_liturgy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get liturgical information for today based on user's hierarchy (authenticated)."""
    return get_liturgy_for_user(date.today(), current_user, db)


@router.get("/my/date/{target_date}")
def get_my_liturgy_by_date(
    target_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get liturgical information for a date based on user's hierarchy (authenticated)."""
    return get_liturgy_for_user(target_date, current_user, db)


@router.get("/date/{target_date}")
def get_liturgy_by_date(
    target_date: date,
    region: str = Query("KE"),
    db: Session = Depends(get_db),
):
    """Get liturgical information and reading references for a specific date."""
    # Get or calculate calendar info
    liturgical_day = db.query(LiturgicalDay).filter(
        LiturgicalDay.date == target_date,
        LiturgicalDay.region == region
    ).first()
    
    if liturgical_day:
        # Use verified data
        calendar_info = {
            "date": target_date.isoformat(),
            "sunday_cycle": liturgical_day.sunday_cycle,
            "weekday_cycle": liturgical_day.weekday_cycle,
            "season": liturgical_day.season,
            "week": liturgical_day.week_number,
            "color": liturgical_day.liturgical_color,
            "celebration": liturgical_day.celebration_name,
            "rank": liturgical_day.celebration_rank,
            "region": liturgical_day.region,
            "verification_status": liturgical_day.verification_status,
        }
    else:
        # Calculate from calendar engine
        calendar_info = get_calendar_info(target_date, region)
    
    # Get reading sets
    reading_sets = []
    if liturgical_day:
        for rs in liturgical_day.reading_sets:
            # Get reading references for this set
            references = []
            for ref in rs.reading_references:
                references.append({
                    "type": ref.reading_type,
                    "book": ref.book,
                    "display_reference": ref.display_reference,
                    "is_alternative": ref.is_alternative,
                    "is_optional": ref.is_optional,
                    "is_primary": ref.is_primary,
                    "sequence": ref.sequence,
                })
            
            reading_sets.append({
                "type": rs.reading_type,
                "selection_status": rs.selection_status,
                "celebration_name": rs.celebration_name,
                "lectionary_number": rs.lectionary_number,
                "authority_level": rs.authority_level,
                "verification_status": rs.verification_status,
                "readings": references,
            })
    
    # Select primary reading set based on precedence
    selected_set = _select_primary_reading_set(reading_sets, calendar_info.get("rank", "Feria"))
    
    return {
        "date": target_date.isoformat(),
        "region": region,
        "celebration": {
            "name": calendar_info.get("celebration"),
            "rank": calendar_info.get("rank"),
        },
        "liturgical": {
            "season": calendar_info.get("season"),
            "week": calendar_info.get("week"),
            "colour": calendar_info.get("color"),
            "sunday_cycle": calendar_info.get("sunday_cycle"),
            "weekday_cycle": calendar_info.get("weekday_cycle"),
        },
        "readings": selected_set.get("readings", []) if selected_set else [],
        "available_reading_sets": reading_sets,
        "source": {
            "name": liturgical_day.source.name if liturgical_day and liturgical_day.source else None,
            "region": region,
        } if liturgical_day else None,
        "verification_status": calendar_info.get("verification_status", "unverified"),
    }


def get_liturgy_for_user(
    target_date: date,
    current_user: User,
    db: Session
):
    """Get liturgical information for a user based on their hierarchy."""
    liturgical_info = get_liturgical_info_for_user(db, current_user, target_date)
    
    # Get reading sets
    liturgical_day = db.query(LiturgicalDay).filter(
        LiturgicalDay.date == target_date,
        LiturgicalDay.region == liturgical_info["region"]
    ).first()
    
    reading_sets = []
    if liturgical_day:
        for rs in liturgical_day.reading_sets:
            references = []
            for ref in rs.reading_references:
                references.append({
                    "type": ref.reading_type,
                    "book": ref.book,
                    "display_reference": ref.display_reference,
                    "is_alternative": ref.is_alternative,
                    "is_optional": ref.is_optional,
                    "is_primary": ref.is_primary,
                    "sequence": ref.sequence,
                })
            
            reading_sets.append({
                "type": rs.reading_type,
                "selection_status": rs.selection_status,
                "celebration_name": rs.celebration_name,
                "lectionary_number": rs.lectionary_number,
                "authority_level": rs.authority_level,
                "verification_status": rs.verification_status,
                "readings": references,
            })
    
    selected_set = _select_primary_reading_set(reading_sets, liturgical_info.get("rank", "Feria"))
    
    return {
        "date": target_date.isoformat(),
        "region": liturgical_info["region"],
        "celebration": {
            "name": liturgical_info.get("celebration"),
            "rank": liturgical_info.get("rank"),
        },
        "liturgical": {
            "season": liturgical_info.get("season"),
            "week": liturgical_info.get("week"),
            "colour": liturgical_info.get("color"),
            "sunday_cycle": liturgical_info.get("sunday_cycle"),
            "weekday_cycle": liturgical_info.get("weekday_cycle"),
        },
        "readings": selected_set.get("readings", []) if selected_set else [],
        "available_reading_sets": reading_sets,
        "source": {
            "name": liturgical_info.get("source"),
            "region": liturgical_info["region"],
        },
        "verification_status": liturgical_info.get("verification_status", "unverified"),
        "scope": liturgical_info.get("scope"),
    }


def _select_primary_reading_set(reading_sets: list, celebration_rank: str) -> Optional[dict]:
    """Select the primary reading set based on celebration rank and precedence rules."""
    if not reading_sets:
        return None
    
    # Group by selection status
    by_status = {}
    for rs in reading_sets:
        status = rs["selection_status"].lower()
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(rs)
    
    rank = celebration_rank.lower()
    
    # Precedence rules
    if rank == "solemnity":
        # Use strictly_proper, fall back to suggested
        return by_status.get("strictly_proper", [])[0] if "strictly_proper" in by_status else by_status.get("suggested", [])[0] if "suggested" in by_status else reading_sets[0]
    
    if rank == "feast":
        # Use strictly_proper or weekday_default
        return by_status.get("strictly_proper", [])[0] if "strictly_proper" in by_status else by_status.get("weekday_default", [])[0] if "weekday_default" in by_status else reading_sets[0]
    
    if "memorial" in rank:
        if "obligatory" in rank or "strictly proper" in rank:
            return by_status.get("strictly_proper", [])[0] if "strictly_proper" in by_status else by_status.get("weekday_default", [])[0] if "weekday_default" in by_status else reading_sets[0]
        # Optional memorial: use weekday_default or common_option
        return by_status.get("weekday_default", [])[0] if "weekday_default" in by_status else by_status.get("common_option", [])[0] if "common_option" in by_status else by_status.get("suggested", [])[0] if "suggested" in by_status else reading_sets[0]
    
    # Default: weekday or feria
    return by_status.get("weekday_default", [])[0] if "weekday_default" in by_status else reading_sets[0]


@router.post("/admin/import")
def import_readings(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import verified liturgical data (admin only)."""
    require_admin(current_user)
    
    # Validate structure
    if "date" not in data or "celebration" not in data:
        raise HTTPException(status_code=400, detail="Missing required fields: date, celebration")
        
    return LiturgicalSyncService.import_verified_data(db, data)


@router.get("/calendar")
def get_calendar(
    start_date: date,
    end_date: date,
    region: str = Query("KE"),
    db: Session = Depends(get_db)
):
    """Get calendar range with liturgical information."""
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must not precede start_date")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=400, detail="Calendar range cannot exceed 366 days")

    verified_days = db.query(LiturgicalDay).filter(
        LiturgicalDay.date >= start_date,
        LiturgicalDay.date <= end_date,
        LiturgicalDay.region == region
    ).all()
    verified_by_date = {day.date: day for day in verified_days}

    calendar = []
    target_date = start_date
    while target_date <= end_date:
        verified_day = verified_by_date.get(target_date)
        if verified_day:
            calendar.append({
                "date": target_date.isoformat(),
                "sunday_cycle": verified_day.sunday_cycle,
                "weekday_cycle": verified_day.weekday_cycle,
                "season": verified_day.season,
                "week": verified_day.week_number,
                "color": verified_day.liturgical_color,
                "celebration": verified_day.celebration_name,
                "rank": verified_day.celebration_rank,
                "region": verified_day.region,
                "verification_status": verified_day.verification_status,
            })
        else:
            # Calculate from calendar engine
            info = get_calendar_info(target_date, region)
            calendar.append(info)
        target_date += timedelta(days=1)
    
    return calendar

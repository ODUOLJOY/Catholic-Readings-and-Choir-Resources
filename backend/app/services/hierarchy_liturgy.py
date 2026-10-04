"""Hierarchy integration for liturgical calendar resolution."""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.liturgical import LiturgicalDay
from app.models.locations import Diocese, Deanery
from app.models.parish import Parish
from app.services.calendar import get_calendar_info


def resolve_user_calendar_region(
    db: Session,
    user: User
) -> tuple[str, Optional[int], Optional[int]]:
    """
    Resolve the appropriate calendar region and scope for a user.
    
    Returns:
        (region_code, diocese_id, parish_id)
        
    Priority:
    1. Parish proper calendar (if parish has proper calendar)
    2. Diocesan proper calendar (if diocese has proper calendar)
    3. National calendar (KE)
    4. General Roman calendar (UNIVERSAL)
    """
    # Check if user has a parish assignment
    if not user.parish_id:
        # User has no parish, fall back to national calendar
        return ("KE", None, None)
    
    parish = db.query(Parish).filter(Parish.id == user.parish_id).first()
    if not parish:
        return ("KE", None, None)
    
    # TODO: Add checks for parish proper calendar and diocesan proper calendar
    # For now, return Kenya national calendar with parish/diocese context
    diocese_id = parish.diocese_id if parish else None
    
    return ("KE", diocese_id, user.parish_id)


def get_liturgical_day_for_user(
    db: Session,
    user: User,
    target_date: date
) -> Optional[LiturgicalDay]:
    """
    Get the appropriate liturgical day for a user based on their hierarchy.
    
    Priority:
    1. Parish proper calendar (if exists and has data for date)
    2. Diocesan proper calendar (if exists and has data for date)
    3. National calendar (KE)
    4. General Roman calendar (UNIVERSAL)
    """
    region, diocese_id, parish_id = resolve_user_calendar_region(db, user)
    
    # Try parish-specific data first
    if parish_id:
        parish_day = db.query(LiturgicalDay).filter(
            LiturgicalDay.date == target_date,
            LiturgicalDay.parish_id == parish_id
        ).first()
        if parish_day:
            return parish_day
    
    # Try diocese-specific data
    if diocese_id:
        diocese_day = db.query(LiturgicalDay).filter(
            LiturgicalDay.date == target_date,
            LiturgicalDay.diocese_id == diocese_id,
            LiturgicalDay.parish_id.is_(None)  # Not parish-specific
        ).first()
        if diocese_day:
            return diocese_day
    
    # Fall back to national calendar
    national_day = db.query(LiturgicalDay).filter(
        LiturgicalDay.date == target_date,
        LiturgicalDay.region == region,
        LiturgicalDay.diocese_id.is_(None),
        LiturgicalDay.parish_id.is_(None)
    ).first()
    
    if national_day:
        return national_day
    
    # No verified data exists, return None (caller can calculate from engine)
    return None


def get_liturgical_info_for_user(
    db: Session,
    user: User,
    target_date: date
) -> dict:
    """
    Get comprehensive liturgical information for a user on a specific date.
    
    This resolves the user's hierarchy and returns the appropriate calendar data.
    """
    liturgical_day = get_liturgical_day_for_user(db, user, target_date)
    
    if liturgical_day:
        # Return verified data from database
        return {
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
            "source": liturgical_day.source.name if liturgical_day.source else None,
            "scope": {
                "parish_id": liturgical_day.parish_id,
                "diocese_id": liturgical_day.diocese_id,
            }
        }
    else:
        # Calculate from calendar engine with user's region
        region, diocese_id, parish_id = resolve_user_calendar_region(db, user)
        calendar_info = get_calendar_info(target_date, region)
        calendar_info["verification_status"] = "unverified"
        calendar_info["source"] = None
        calendar_info["scope"] = {
            "parish_id": parish_id,
            "diocese_id": diocese_id,
        }
        return calendar_info

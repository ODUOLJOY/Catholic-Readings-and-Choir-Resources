from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.report import ContentReport
from app.models.user import User
from app.routes.auth_dependency import get_current_user, require_admin

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.post("/")
def create_report(
    resource_type: str,
    resource_id: int,
    reason: str,
    description: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = ContentReport(
        reporter_id=current_user.id,
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason,
        description=description,
    )
    db.add(report)
    db.commit()
    return {"message": "Report submitted."}

@router.get("/", dependencies=[Depends(require_admin)])
def get_reports(db: Session = Depends(get_db)):
    return db.query(ContentReport).all()

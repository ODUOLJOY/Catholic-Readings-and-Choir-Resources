from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Reading

router = APIRouter(prefix="/readings")


@router.get("/")
def get_readings(db: Session = Depends(get_db)):
    return db.query(Reading).all()
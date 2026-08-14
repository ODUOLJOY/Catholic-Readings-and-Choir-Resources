from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
import shutil

from app.db.database import get_db
from app.models.readings import Reading
from app.models.user import User
from app.auth.security import decode_token
from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def require_admin(user: User):
    if user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    # Count admins (both admin and super_admin roles)
    admins_count = db.query(User).filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    return {
        "users": db.query(User).count(),
        "admins": admins_count,
        "readings": db.query(Reading).filter(
            Reading.published == True
        ).count(),
        "choir_resources": 0,  # TODO: implement when ChoirResource model is created
        "pending_uploads": db.query(Reading).filter(
            Reading.approved == False
        ).count(),
        "pending_reports": 0,  # TODO: implement when Report model is created
    }


@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(User).order_by(User.created_at.desc()).all()


@router.put("/users/{user_id}/role")
def change_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if role not in ["user", "admin", "super_admin"]:
        raise HTTPException(400, "Invalid role.")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.role = role

    db.commit()
    db.refresh(user)

    return {
        "message": "Role updated successfully.",
        "role": role,
    }


@router.put("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.is_active = False

    db.commit()

    return {
        "message": "User disabled successfully."
    }


@router.put("/users/{user_id}/enable")
def enable_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    user.is_active = True

    db.commit()

    return {
        "message": "User enabled successfully."
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found.")

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully."
    }


@router.get("/pending")
def pending_readings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return (
        db.query(Reading)
        .filter(Reading.approved == False)
        .order_by(Reading.created_at.desc())
        .all()
    )


@router.put("/approve/{reading_id}")
def approve_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    reading = (
        db.query(Reading)
        .filter(Reading.id == reading_id)
        .first()
    )

    if not reading:
        raise HTTPException(404, "Reading not found.")

    reading.approved = True
    reading.published = True

    db.commit()
    db.refresh(reading)

    return {
        "message": "Reading approved successfully."
    }


@router.delete("/readings/{reading_id}")
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    reading = db.query(Reading).filter(
        Reading.id == reading_id
    ).first()

    if not reading:
        raise HTTPException(404, "Reading not found.")

    db.delete(reading)
    db.commit()

    return {
        "message": "Reading deleted successfully."
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    extension = Path(file.filename).suffix.lower()

    allowed = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".mp3",
        ".wav",
        ".mp4",
        ".mov",
    ]

    if extension not in allowed:
        raise HTTPException(
            400,
            "Unsupported file type.",
        )

    filename = f"{uuid4()}{extension}"

    destination = UPLOAD_DIR / filename

    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Upload successful.",
        "filename": filename,
        "url": f"/uploads/{filename}",
    }
}
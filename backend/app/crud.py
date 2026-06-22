from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models, schemas


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_phone(db: Session, phone_number: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()


def get_users_count(db: Session) -> int:
    return db.query(models.User).count()


def create_user(db: Session, user: schemas.UserCreate, role: str = "user") -> models.User:
    hashed_password = models.User.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        phone_number=user.phone_number,
        role=role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_user_with_role(db: Session, user: schemas.UserCreate, role: str = "admin") -> models.User:
    return create_user(db, user, role=role)


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not models.User.verify_password(password, user.hashed_password):
        return None
    return user


def create_reading(db: Session, reading: schemas.ReadingCreate, user_id: int) -> models.Reading:
    db_reading = models.Reading(
        date=reading.date,
        liturgical_year=reading.liturgical_year,
        feast=reading.feast,
        language=reading.language,
        first_reading=reading.first_reading,
        responsorial_psalm=reading.responsorial_psalm,
        second_reading=reading.second_reading,
        gospel=reading.gospel,
        reflection=reading.reflection,
        status=reading.status or "pending_review",
        uploaded_by=user_id,
    )
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


def get_reading_by_id(db: Session, reading_id: int) -> Optional[models.Reading]:
    return db.query(models.Reading).filter(models.Reading.id == reading_id).first()


def get_readings_by_date_and_language(db: Session, date_value: date, language: str) -> List[models.Reading]:
    return (
        db.query(models.Reading)
        .filter(models.Reading.date == date_value)
        .filter(models.Reading.language == language)
        .filter(models.Reading.status == "published")
        .all()
    )


def get_today_readings(db: Session, language: str) -> List[models.Reading]:
    today = datetime.utcnow().date()
    return get_readings_by_date_and_language(db, today, language)


def search_readings(db: Session, date_value: Optional[date], language: Optional[str]) -> List[models.Reading]:
    query = db.query(models.Reading).filter(models.Reading.status == "published")
    if date_value:
        query = query.filter(models.Reading.date == date_value)
    if language:
        query = query.filter(models.Reading.language == language)
    return query.order_by(models.Reading.date.desc()).all()


def get_pending_readings(db: Session) -> List[models.Reading]:
    return db.query(models.Reading).filter(models.Reading.status == "pending_review").order_by(models.Reading.date.desc()).all()


def approve_reading(db: Session, reading_id: int) -> Optional[models.Reading]:
    reading = get_reading_by_id(db, reading_id)
    if not reading:
        return None
    reading.status = "published"
    db.commit()
    db.refresh(reading)
    return reading


def add_favorite(db: Session, user_id: int, reading_id: int) -> models.Favorite:
    favorite = models.Favorite(user_id=user_id, reading_id=reading_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


def get_favorites_for_user(db: Session, user_id: int) -> List[models.Favorite]:
    return db.query(models.Favorite).filter(models.Favorite.user_id == user_id).all()


def create_report(db: Session, report: schemas.ReportCreate, reporter_id: int) -> models.Report:
    db_report = models.Report(
        reporting_user_id=reporter_id,
        reading_id=report.reading_id,
        reason=report.reason,
        details=report.details,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def get_reports(db: Session) -> List[models.Report]:
    return db.query(models.Report).order_by(models.Report.created_at.desc()).all()


def create_media_upload(
    db: Session,
    user_id: int,
    reading_id: Optional[int],
    filename: str,
    file_path: str,
    content_type: str,
    resource_type: str,
) -> models.Base:
    upload_kwargs = {
        "user_id": user_id,
        "reading_id": reading_id,
        "filename": filename,
        "file_path": file_path,
        "content_type": content_type,
        "status": "pending_review",
    }

    if resource_type == "audio":
        upload_record = models.AudioUpload(**upload_kwargs)
    elif resource_type == "video":
        upload_record = models.VideoUpload(**upload_kwargs)
    elif resource_type == "pdf":
        upload_record = models.PdfUpload(**upload_kwargs)
    elif resource_type == "image":
        upload_record = models.ImageUpload(**upload_kwargs)
    elif resource_type == "music":
        upload_record = models.MusicNote(**upload_kwargs)
    else:
        raise ValueError("Unsupported resource type")

    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)
    return upload_record


def get_pending_media_uploads(db: Session) -> List[models.Base]:
    uploads = []
    uploads.extend(db.query(models.AudioUpload).filter(models.AudioUpload.status == "pending_review").all())
    uploads.extend(db.query(models.VideoUpload).filter(models.VideoUpload.status == "pending_review").all())
    uploads.extend(db.query(models.PdfUpload).filter(models.PdfUpload.status == "pending_review").all())
    uploads.extend(db.query(models.ImageUpload).filter(models.ImageUpload.status == "pending_review").all())
    uploads.extend(db.query(models.MusicNote).filter(models.MusicNote.status == "pending_review").all())
    return uploads


def get_media_upload_by_id(db: Session, resource_type: str, upload_id: int) -> Optional[models.Base]:
    model_map = {
        "audio": models.AudioUpload,
        "video": models.VideoUpload,
        "pdf": models.PdfUpload,
        "image": models.ImageUpload,
        "music": models.MusicNote,
    }
    model = model_map.get(resource_type)
    if model is None:
        return None
    return db.query(model).filter(model.id == upload_id).first()


def approve_media_upload(db: Session, resource_type: str, upload_id: int) -> Optional[models.Base]:
    upload = get_media_upload_by_id(db, resource_type, upload_id)
    if upload is None:
        return None
    upload.status = "approved"
    db.commit()
    db.refresh(upload)
    return upload


def cache_reading(db: Session, user_id: int, reading_id: int) -> models.OfflineCache:
    cached = models.OfflineCache(user_id=user_id, reading_id=reading_id)
    db.add(cached)
    db.commit()
    db.refresh(cached)
    return cached


def get_cached_readings(db: Session, user_id: int) -> List[models.Reading]:
    reading_ids = [item.reading_id for item in db.query(models.OfflineCache).filter(models.OfflineCache.user_id == user_id).all()]
    return db.query(models.Reading).filter(models.Reading.id.in_(reading_ids)).all()

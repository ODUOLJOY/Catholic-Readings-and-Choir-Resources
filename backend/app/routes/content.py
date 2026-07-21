from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.content import Content
from app.models.user import User
from app.routes.auth_dependency import (
    get_current_user,
    require_admin,
)

router = APIRouter(
    prefix="/api/content",
    tags=["Content"],
)


@router.get("/")
def get_content(
    content_type: str | None = None,
    language: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Content).filter(
        Content.is_published == True
    )

    if content_type:
        query = query.filter(Content.content_type == content_type)

    if language:
        query = query.filter(Content.language == language)

    return query.order_by(
        Content.created_at.desc()
    ).all()


@router.get("/{content_id}")
def get_content_by_id(
    content_id: int,
    db: Session = Depends(get_db),
):
    content = (
        db.query(Content)
        .filter(Content.id == content_id)
        .first()
    )

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found."
        )

    return content


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
def create_content(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = Content(
        title=payload["title"],
        body=payload["body"],
        content_type=payload["content_type"],
        language=payload.get("language", "English"),
        is_published=payload.get("is_published", True),
        created_by=current_user.id,
    )

    db.add(content)
    db.commit()
    db.refresh(content)

    return content


@router.put("/{content_id}")
def update_content(
    content_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(Content)
        .filter(Content.id == content_id)
        .first()
    )

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found."
        )

    content.title = payload.get("title", content.title)
    content.body = payload.get("body", content.body)
    content.content_type = payload.get(
        "content_type",
        content.content_type,
    )
    content.language = payload.get(
        "language",
        content.language,
    )
    content.is_published = payload.get(
        "is_published",
        content.is_published,
    )

    db.commit()
    db.refresh(content)

    return content


@router.delete("/{content_id}")
def delete_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(Content)
        .filter(Content.id == content_id)
        .first()
    )

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found."
        )

    db.delete(content)
    db.commit()

    return {
        "message": "Content deleted successfully."
    }


@router.get("/search/{keyword}")
def search_content(
    keyword: str,
    db: Session = Depends(get_db),
):
    return (
        db.query(Content)
        .filter(
            Content.title.ilike(f"%{keyword}%")
            | Content.body.ilike(f"%{keyword}%")
        )
        .filter(Content.is_published == True)
        .all()
    )


@router.post("/{content_id}/publish")
def publish_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(Content)
        .filter(Content.id == content_id)
        .first()
    )

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found."
        )

    content.is_published = True
    db.commit()

    return {
        "message": "Content published successfully."
    }


@router.post("/{content_id}/unpublish")
def unpublish_content(
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(Content)
        .filter(Content.id == content_id)
        .first()
    )

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Content not found."
        )

    content.is_published = False
    db.commit()

    return {
        "message": "Content unpublished successfully."
    }
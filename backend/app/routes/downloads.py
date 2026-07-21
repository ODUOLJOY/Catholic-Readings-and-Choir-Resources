from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.download import Download
from app.models.choir import ChoirResource
from app.models.user import User
from app.routes.auth_dependency import get_current_user

router = APIRouter(
    prefix="/api/downloads",
    tags=["Downloads"],
)


@router.get("/")
def my_downloads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Download)
        .filter(Download.user_id == current_user.id)
        .order_by(Download.downloaded_at.desc())
        .all()
    )


@router.post("/{resource_id}")
def download_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = (
        db.query(ChoirResource)
        .filter(
            ChoirResource.id == resource_id,
            ChoirResource.is_approved == True,
        )
        .first()
    )

    if not resource:
        raise HTTPException(
            status_code=404,
            detail="Resource not found."
        )

    existing = (
        db.query(Download)
        .filter(
            Download.user_id == current_user.id,
            Download.resource_id == resource.id,
        )
        .first()
    )

    if not existing:
        download = Download(
            user_id=current_user.id,
            resource_id=resource.id,
        )

        db.add(download)
        db.commit()

    return {
        "message": "Download recorded successfully.",
        "file_name": resource.original_name,
        "file_url": resource.file_path,
    }


@router.delete("/{download_id}")
def remove_download(
    download_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    download = (
        db.query(Download)
        .filter(
            Download.id == download_id,
            Download.user_id == current_user.id,
        )
        .first()
    )

    if not download:
        raise HTTPException(
            status_code=404,
            detail="Download not found."
        )

    db.delete(download)
    db.commit()

    return {
        "message": "Download removed successfully."
    }


@router.delete("/")
def clear_download_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    (
        db.query(Download)
        .filter(Download.user_id == current_user.id)
        .delete()
    )

    db.commit()

    return {
        "message": "Download history cleared."
    }


@router.get("/count")
def download_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = (
        db.query(Download)
        .filter(Download.user_id == current_user.id)
        .count()
    )

    return {
        "downloads": total
    }
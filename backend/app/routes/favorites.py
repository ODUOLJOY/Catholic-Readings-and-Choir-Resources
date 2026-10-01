from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.favorite import Favorite
from app.schemas.favorite import Favorite as FavoriteSchema, FavoriteCreate
from app.routes.auth_dependency import get_current_user
from app.models.user import User

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("/", response_model=List[FavoriteSchema])
def get_favorites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Favorite).filter(Favorite.user_id == current_user.id).all()

@router.post("/", response_model=FavoriteSchema)
def create_favorite(favorite_in: FavoriteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check if already favorited
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.resource_type == favorite_in.resource_type,
        Favorite.target_resource_id == favorite_in.target_resource_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already favorited")
    
    new_favorite = Favorite(
        user_id=current_user.id,
        resource_type=favorite_in.resource_type,
        target_resource_id=favorite_in.target_resource_id
    )
    db.add(new_favorite)
    db.commit()
    db.refresh(new_favorite)
    return new_favorite

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    favorite = db.query(Favorite).filter(Favorite.id == id, Favorite.user_id == current_user.id).first()
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
    
    db.delete(favorite)
    db.commit()
    return None

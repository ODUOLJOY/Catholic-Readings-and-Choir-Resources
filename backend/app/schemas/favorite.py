from pydantic import BaseModel
from datetime import datetime

class FavoriteBase(BaseModel):
    resource_type: str
    target_resource_id: int

class FavoriteCreate(FavoriteBase):
    pass

class Favorite(FavoriteBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

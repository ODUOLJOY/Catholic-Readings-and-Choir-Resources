from fastapi import Depends
from app.db.database import get_db
from app.models.user import User
from app.routes.auth_dependency import (
    get_current_user,
    require_moderator as get_moderator_user,
    require_admin as get_admin_user,
    require_super_admin as get_super_admin,
)

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user

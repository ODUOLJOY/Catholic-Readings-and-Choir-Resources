from typing import Generator

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

security = HTTPBearer(auto_error=True)


# ------------------------------------
# Database Dependency
# ------------------------------------

def get_database() -> Generator[Session, None, None]:
    yield from get_db()


# ------------------------------------
# Auth Service
# ------------------------------------

def get_auth_service(
    db: Session = Depends(get_database),
) -> AuthService:
    return AuthService(db)


# ------------------------------------
# Current User
# ------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    auth: AuthService = Depends(get_auth_service),
) -> User:

    token = credentials.credentials

    try:
        user = auth.get_current_user(token)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    return user


# ------------------------------------
# Verified User
# ------------------------------------

def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:

    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address.",
        )

    return current_user


# ------------------------------------
# Admin
# ------------------------------------

def get_admin_user(
    current_user: User = Depends(get_verified_user),
) -> User:

    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )

    return current_user


# ------------------------------------
# Super Admin
# ------------------------------------

def get_super_admin(
    current_user: User = Depends(get_verified_user),
) -> User:

    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super administrator privileges required.",
        )

    return current_user
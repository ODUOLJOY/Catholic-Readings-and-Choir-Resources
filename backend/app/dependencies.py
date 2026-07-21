from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        email = payload.get("sub")

        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Inactive account.",
        )

    return current_user


def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:

    if current_user.role not in [
        "ADMIN",
        "SUPER_ADMIN",
    ]:
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

    return current_user


def get_super_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:

    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Super administrator access required.",
        )

    return current_user
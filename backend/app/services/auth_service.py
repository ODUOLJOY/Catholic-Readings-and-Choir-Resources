from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# =====================================================
# PASSWORD
# =====================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# =====================================================
# JWT TOKENS
# =====================================================

def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )


# =====================================================
# USERS
# =====================================================

def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[User]:

    user = (
        db.query(User)
        .filter(User.email == email.lower())
        .first()
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.hashed_password,
    ):
        return None

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled.",
        )

    user.last_login = datetime.utcnow()

    db.commit()

    return user


def create_user(
    db: Session,
    full_name: str,
    email: str,
    password: str,
    parish_id: Optional[int] = None,
) -> User:

    exists = (
        db.query(User)
        .filter(User.email == email.lower())
        .first()
    )

    if exists:
        raise HTTPException(
            status_code=400,
            detail="Email already exists.",
        )

    user = User(
        full_name=full_name,
        email=email.lower(),
        hashed_password=hash_password(password),
        parish_id=parish_id,
        role="user",
        is_active=True,
        is_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


class AuthService:
    """Compatibility facade for legacy route imports."""

    @staticmethod
    def create_user(*args, **kwargs):
        return create_user(*args, **kwargs)

    @staticmethod
    def authenticate_user(*args, **kwargs):
        return authenticate_user(*args, **kwargs)

    @staticmethod
    def reset_password(*args, **kwargs):
        return reset_password(*args, **kwargs)

    @staticmethod
    def verify_email(*args, **kwargs):
        return verify_email(*args, **kwargs)

    @staticmethod
    def now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def create_password_reset_token(user: User) -> str:
        return generate_reset_token(user)

    @staticmethod
    def verify_refresh_token(token: str) -> dict:
        payload = verify_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token.")
        return payload


def get_current_user(
    db: Session,
    token: str,
) -> User:

    payload = verify_token(token)

    user = (
        db.query(User)
        .filter(User.id == int(payload["sub"]))
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
        )

    return user


# =====================================================
# PASSWORD RESET
# =====================================================

def generate_reset_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(hours=1)

    payload = {
        "sub": str(user.id),
        "type": "reset",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def reset_password(
    db: Session,
    token: str,
    new_password: str,
):

    payload = verify_token(token)

    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=400,
            detail="Invalid reset token.",
        )

    user = (
        db.query(User)
        .filter(User.id == int(payload["sub"]))
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    user.password_hash = hash_password(
        new_password
    )

    db.commit()


# =====================================================
# EMAIL VERIFICATION
# =====================================================

def generate_email_verification_token(
    user: User,
) -> str:

    expire = datetime.utcnow() + timedelta(days=1)

    payload = {
        "sub": str(user.id),
        "type": "verify",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_email(
    db: Session,
    token: str,
):

    payload = verify_token(token)

    if payload.get("type") != "verify":
        raise HTTPException(
            status_code=400,
            detail="Invalid verification token.",
        )

    user = (
        db.query(User)
        .filter(User.id == int(payload["sub"]))
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    user.is_verified = True

    db.commit()
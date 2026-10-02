from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.auth import RefreshSession
from app.auth.security import hash_password, verify_password

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

def create_refresh_session(
    db: Session,
    user_id: int,
    token_hash: str,
    jti: str,
    expires_at: datetime,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RefreshSession:
    session = RefreshSession(
        user_id=user_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def revoke_refresh_session(db: Session, token_hash: str):
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int):
    db.query(RefreshSession).filter(
        RefreshSession.user_id == user_id,
        RefreshSession.revoked_at == None,
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()


def get_refresh_session(
    db: Session, jti: str, token_hash: str
) -> Optional[RefreshSession]:
    return (
        db.query(RefreshSession)
        .filter(
            RefreshSession.jti == jti,
            RefreshSession.token_hash == token_hash,
        )
        .first()
    )


def ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not user.password_reset_token or not hmac.compare_digest(
        user.password_reset_token,
        token_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or already used reset token.",
        )

    user.hashed_password = hash_password(
        new_password
    )
    user.password_reset_token = None

    db.commit()

    revoke_all_user_sessions(db, user.id)


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
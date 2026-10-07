from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import re
import secrets
import string
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.auth import ExternalIdentity, RefreshSession
from app.auth.security import hash_password, verify_password
from app.services.google_auth import PROVIDER_GOOGLE, GoogleIdentity

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

logger = logging.getLogger(__name__)

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


def _generate_unique_username(db: Session, email: str) -> str:
    """Build a unique, human-readable username from the email local-part.

    The ``username`` column is NOT NULL with a UNIQUE constraint, so every
    INSERT must supply a value. We derive one from the email and append a short
    random suffix when the base name is already taken.
    """
    local = email.split("@")[0]
    base = re.sub(r"[^a-zA-Z0-9._-]", "", local)[:15] or "user"
    base = base.lower()
    candidate = base
    while db.query(User).filter(User.username == candidate).first() is not None:
        candidate = f"{base}_{secrets.token_hex(3)}"
    return candidate or f"user_{secrets.token_hex(3)}"


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
        username=_generate_unique_username(db, email),
        hashed_password=hash_password(password),
        parish_id=parish_id,
        role="user",
        is_active=True,
        is_verified=False,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # Inspect the actual PostgreSQL error code instead of assuming every
        # uniqueness conflict is a duplicate email. 23505 = unique violation
        # (could be email or username); 23502 = NOT NULL violation (previously
        # reported as "Email already registered" when username was missing).
        pgcode = getattr(getattr(error, "orig", None), "pgcode", None)
        if pgcode == "23505":
            constraint = getattr(
                getattr(error, "orig", None), "diag", None
            )
            constraint_name = getattr(constraint, "constraint_name", None) if constraint else None
            if constraint_name and "email" in constraint_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered.",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken.",
            ) from error
        logger.exception("Unexpected IntegrityError during user creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user.",
        ) from error
    db.refresh(user)

    return user


def login_with_google_identity(
    db: Session,
    identity: GoogleIdentity,
) -> tuple[User, bool]:
    """Resolve a verified Google identity to a local user.

    Returns ``(user, created)``. The Google subject is the permanent key; an
    email is only ever used to *link* to an already-trusted local account and
    never to create a trusted identity on its own.
    """

    linked = (
        db.query(ExternalIdentity)
        .filter(
            ExternalIdentity.provider == PROVIDER_GOOGLE,
            ExternalIdentity.provider_subject == identity.subject,
        )
        .first()
    )

    if linked is not None:
        user = db.query(User).filter(User.id == linked.user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Linked account no longer exists.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled.",
            )
        return user, False

    if not identity.email or not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not provide a verified email address.",
        )

    email = identity.email.lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    created = False

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled.",
            )
        # Only link to an existing account whose email ownership is already
        # proven, or to the operator-managed super administrator. This blocks
        # takeover of a pre-registered, unverified account that shares the
        # same email as the Google identity.
        if not (user.is_verified or user.role == "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An account with this email already exists. "
                    "Sign in with your password to link Google sign-in."
                ),
            )
    else:
        user = User(
            full_name=identity.name or email.split("@")[0],
            email=email,
            username=_generate_unique_username(db, email),
            hashed_password=hash_password(secrets.token_urlsafe(48)),
            role="user",
            is_active=True,
            is_verified=True,
            profile_picture=identity.picture,
        )
        db.add(user)
        db.flush()
        created = True

    db.add(
        ExternalIdentity(
            user_id=user.id,
            provider=PROVIDER_GOOGLE,
            provider_subject=identity.subject,
            email_at_link=email,
        )
    )

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        logger.warning("Concurrent Google identity link was prevented.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Google account is already linked.",
        ) from error

    db.refresh(user)
    return user, created


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

    subject = payload.get("sub")
    try:
        user_pk = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
        )

    user = (
        db.query(User)
        .filter(User.id == user_pk)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account has been disabled.",
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

    subject = payload.get("sub")
    try:
        user_pk = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid reset token.",
        )

    user = (
        db.query(User)
        .filter(User.id == user_pk)
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


def issue_email_verification_token(db: Session, user: User) -> str:
    """Create a one-time email verification token and store only its hash."""

    token = generate_email_verification_token(user)
    user.email_verification_token = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
    db.commit()
    return token


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

    subject = payload.get("sub")
    try:
        user_pk = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification token.",
        )

    user = (
        db.query(User)
        .filter(User.id == user_pk)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not user.email_verification_token or not hmac.compare_digest(
        user.email_verification_token,
        token_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or already used verification token.",
        )

    user.is_verified = True
    user.email_verification_token = None

    db.commit()
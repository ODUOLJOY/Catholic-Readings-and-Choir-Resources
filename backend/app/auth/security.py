from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)

ALGORITHM = settings.ALGORITHM


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update(
        {
            "exp": expire,
            "type": "access",
            "jti": str(uuid.uuid4()),
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(
    data: dict,
    jti: Optional[str] = None,
) -> str:
    to_encode = data.copy()

    expire = refresh_token_expires_at()

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": jti or str(uuid.uuid4()),
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def refresh_token_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )


def decode_token(
    token: str,
    expected_type: Optional[str] = None
):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if expected_type and payload.get("type") != expected_type:
            return None

        return payload
    except JWTError:
        return None


def decode_access_token(token: str, expected_type: Optional[str] = "access"):
    return decode_token(token, expected_type=expected_type)


def decode_refresh_token(token: str):
    return decode_token(token, expected_type="refresh")

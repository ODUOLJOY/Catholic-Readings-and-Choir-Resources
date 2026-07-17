from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------
    # Password Hashing
    # ------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        return pwd_context.verify(password, hashed_password)

    # ------------------------
    # JWT Tokens
    # ------------------------

    @staticmethod
    def create_access_token(user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "type": "access",
            "exp": expire,
        }

        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

    @staticmethod
    def create_refresh_token(user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
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

    @staticmethod
    def decode_token(token: str):
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

    # ------------------------
    # Registration
    # ------------------------

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:

        existing = (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        if existing:
            raise ValueError("Email already exists.")

        user = User(
            full_name=full_name.strip(),
            email=email.lower().strip(),
            password_hash=self.hash_password(password),
            role=role,
            is_active=True,
            is_verified=False,
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user

    # ------------------------
    # Login
    # ------------------------

    def authenticate(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:

        user = (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

        if not user:
            return None

        if not user.is_active:
            return None

        if user.locked_until and user.locked_until > datetime.now(
            timezone.utc
        ):
            return None

        if not self.verify_password(
            password,
            user.password_hash,
        ):
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(
                    timezone.utc
                ) + timedelta(minutes=15)

            self.db.commit()
            return None

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)

        self.db.commit()

        return user

    # ------------------------
    # Get User
    # ------------------------

    def get_user(self, user_id: int) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .first()
        )

    def get_user_by_email(
        self,
        email: str,
    ) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.email == email.lower())
            .first()
        )

    # ------------------------
    # Token User
    # ------------------------

    def get_current_user(
        self,
        token: str,
    ) -> User:

        try:
            payload = self.decode_token(token)
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError):
            raise ValueError("Invalid token.")

        user = self.get_user(user_id)

        if not user:
            raise ValueError("User not found.")

        return user

    # ------------------------
    # Update Password
    # ------------------------

    def update_password(
        self,
        user: User,
        new_password: str,
    ):

        user.password_hash = self.hash_password(
            new_password
        )

        self.db.commit()

    # ------------------------
    # Verify Email
    # ------------------------

    def verify_email(self, user: User):

        user.is_verified = True
        user.verification_token = None

        self.db.commit()

    # ------------------------
    # Refresh Tokens
    # ------------------------

    def generate_tokens(self, user: User):

        return {
            "access_token": self.create_access_token(user),
            "refresh_token": self.create_refresh_token(user),
            "token_type": "bearer",
        }
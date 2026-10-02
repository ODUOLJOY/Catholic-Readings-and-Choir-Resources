import hashlib
import logging
import uuid

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    ForgotPasswordRequest,
    LogoutRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    ChangePasswordRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    AuthService,
    create_refresh_session,
    ensure_utc,
    generate_reset_token,
    get_refresh_session,
    revoke_all_user_sessions,
    revoke_refresh_session,
)
from app.services.email import (
    EmailDeliveryError,
    email_delivery_configured,
    send_password_reset_email,
)
from app.routes.auth_dependency import get_current_user
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    refresh_token_expires_at,
    verify_password,
    hash_password,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)
logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone_number: str | None = Field(default=None, max_length=30)
    language: Literal["English", "Kiswahili"] | None = None


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(User)
        .filter(User.email == payload.email.lower())
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered.",
        )

    user = AuthService.create_user(
        db=db,
        full_name=payload.full_name,
        email=payload.email.lower(),
        password=payload.password,
    )

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = AuthService.authenticate_user(
        db,
        payload.email.lower(),
        payload.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account disabled.",
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
        }
    )

    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
        },
        jti=jti,
    )

    create_refresh_session(
        db,
        user_id=user.id,
        token_hash=_hash_token(refresh_token),
        jti=jti,
        expires_at=refresh_token_expires_at(),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    user.last_login = AuthService.now()

    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def current_user(
    user: User = Depends(get_current_user),
):
    return user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one profile field to update.")

    if "full_name" in updates:
        full_name = (updates["full_name"] or "").strip()
        if not full_name:
            raise HTTPException(status_code=400, detail="Full name cannot be empty.")
        user.full_name = full_name
    if "phone_number" in updates:
        phone_number = updates["phone_number"]
        user.phone_number = phone_number.strip() or None if phone_number else None
    if "language" in updates:
        user.language = updates["language"]

    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    revoke_all_user_sessions(db, user.id)
    return {"message": "Password changed successfully."}


@router.post("/refresh")
def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    payload = decode_refresh_token(refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    jti = payload.get("jti")
    subject = payload.get("sub")
    if not jti or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    session = get_refresh_session(db, jti, _hash_token(refresh_token))
    now = datetime.now(timezone.utc)
    if session is None or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is no longer valid.",
        )

    expires_at = ensure_utc(session.expires_at)
    if expires_at is not None and expires_at <= now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session has expired.",
        )

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if not user.is_active:
        revoke_all_user_sessions(db, user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled.",
        )

    session.revoked_at = now
    session.last_used_at = now

    new_jti = str(uuid.uuid4())
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        jti=new_jti,
    )
    create_refresh_session(
        db,
        user_id=user.id,
        token_hash=_hash_token(new_refresh_token),
        jti=new_jti,
        expires_at=refresh_token_expires_at(),
    )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
        }
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    payload: LogoutRequest | None = None,
    db: Session = Depends(get_db),
):
    if payload and payload.refresh_token:
        revoke_refresh_session(db, _hash_token(payload.refresh_token))
    return {
        "message": "Logged out successfully."
    }


@router.post("/logout-all")
def logout_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    revoke_all_user_sessions(db, user.id)
    return {
        "message": "All sessions have been revoked."
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    if not email_delivery_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email delivery is not configured.",
        )

    user = (
        db.query(User)
        .filter(User.email == str(payload.email).lower())
        .first()
    )

    if user and user.is_active:
        token = generate_reset_token(user)
        user.password_reset_token = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()
        db.commit()
        try:
            send_password_reset_email(user.email, token)
        except EmailDeliveryError:
            user.password_reset_token = None
            db.commit()
            logger.error("Password reset email delivery failed.")

    return {
        "message": "If the account exists and email delivery is available, password reset instructions will be sent.",
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    user = AuthService.reset_password(
        db=db,
        token=payload.token,
        new_password=payload.password,
    )

    return {
        "message": "Password updated successfully."
    }


@router.post("/verify-email")
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    user = AuthService.verify_email(
        db=db,
        token=token,
    )

    return {
        "message": "Email verified successfully."
    }

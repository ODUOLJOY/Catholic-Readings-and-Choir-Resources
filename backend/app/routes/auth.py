import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    ForgotPasswordRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService, generate_reset_token
from app.services.email import (
    EmailDeliveryError,
    email_delivery_configured,
    send_password_reset_email,
)
from app.routes.auth_dependency import get_current_user
from app.auth.security import (
    create_access_token,
    create_refresh_token,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)
logger = logging.getLogger(__name__)

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

    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
        }
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


@router.post("/refresh")
def refresh_token(
    refresh_token: str,
):
    payload = AuthService.verify_refresh_token(
        refresh_token
    )

    access_token = create_access_token(
        data={
            "sub": payload["sub"],
            "role": payload.get("role", "user"),
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout():
    return {
        "message": "Logged out successfully."
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
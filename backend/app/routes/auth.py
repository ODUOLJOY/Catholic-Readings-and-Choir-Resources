from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.auth.security import (
    create_access_token,
    create_refresh_token,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


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
    user: User = Depends(AuthService.get_current_user),
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
    email: str,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == email.lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    token = AuthService.create_password_reset_token(user)

    return {
        "message": "Password reset token generated.",
        "reset_token": token,
    }


@router.post("/reset-password")
def reset_password(
    token: str,
    password: str,
    db: Session = Depends(get_db),
):
    user = AuthService.reset_password(
        db=db,
        token=token,
        new_password=password,
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
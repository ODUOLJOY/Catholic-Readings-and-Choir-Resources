"""
Schema exports for the Catholic Readings & Choir Resources App.
"""

# Authentication
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    Token,
    TokenData,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

# Users
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfile,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "RegisterRequest",
    "Token",
    "TokenData",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",

    # Users
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserProfile",
]
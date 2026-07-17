from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# -------------------------
# Registration
# -------------------------

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


# -------------------------
# Login
# -------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# -------------------------
# JWT Tokens
# -------------------------

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# -------------------------
# Email Verification
# -------------------------

class VerifyEmailRequest(BaseModel):
    token: str


# -------------------------
# Forgot Password
# -------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


# -------------------------
# Change Password
# -------------------------

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# -------------------------
# Authenticated User
# -------------------------

class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool
    profile_picture: str | None = None
    phone_number: str | None = None
    created_at: datetime
    updated_at: datetime


# -------------------------
# Generic Response
# -------------------------

class MessageResponse(BaseModel):
    message: str
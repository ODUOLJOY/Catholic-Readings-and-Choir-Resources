from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ==========================================
# Base User Schema
# ==========================================

class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    parish_id: Optional[int] = None


# ==========================================
# Create User
# ==========================================

class UserCreate(UserBase):
    password: str


# ==========================================
# Update User
# ==========================================

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    parish_id: Optional[int] = None
    profile_image: Optional[str] = None


# ==========================================
# Public User
# ==========================================

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_verified: bool
    profile_image: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Admin User View
# ==========================================

class UserAdminResponse(UserResponse):
    updated_at: Optional[datetime] = None


# ==========================================
# User Profile
# ==========================================

class UserProfile(UserResponse):
    bookmarked_readings: int = 0
    downloaded_resources: int = 0
    uploaded_resources: int = 0


# ==========================================
# Password Change
# ==========================================

class ChangePassword(BaseModel):
    current_password: str
    new_password: str


# ==========================================
# Email Verification
# ==========================================

class VerifyEmail(BaseModel):
    token: str


# ==========================================
# Password Reset
# ==========================================

class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str


# ==========================================
# Simple API Response
# ==========================================

class MessageResponse(BaseModel):
    message: str
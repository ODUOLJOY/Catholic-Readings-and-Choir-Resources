from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr


class PhoneLogin(BaseModel):
    phone_number: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class UserCreate(UserBase):
    password: str


class AdminCreate(UserCreate):
    role: Optional[str] = "admin"


class UserRead(UserBase):
    id: int
    role: str
    is_active: bool

    class Config:
        orm_mode = True


class ReadingBase(BaseModel):
    date: date
    liturgical_year: str
    feast: Optional[str] = None
    language: str
    first_reading: str
    responsorial_psalm: str
    second_reading: Optional[str] = None
    gospel: str
    reflection: Optional[str] = None


class ReadingCreate(ReadingBase):
    status: Optional[str] = "pending_review"


class ReadingRead(ReadingBase):
    id: int
    status: str
    uploaded_by: Optional[int] = None

    class Config:
        orm_mode = True


class FavoriteRead(BaseModel):
    id: int
    reading: ReadingRead

    class Config:
        orm_mode = True


class ReportCreate(BaseModel):
    reading_id: int
    reason: str
    details: Optional[str] = None


class ReportRead(BaseModel):
    id: int
    reading_id: int
    reason: str
    details: Optional[str] = None
    reporter_id: int

    class Config:
        orm_mode = True

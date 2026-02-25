from datetime import datetime
from pydantic import BaseModel
from app.models.user import UserRole


class UserBase(BaseModel):
    email: str
    full_name: str = ""
    class_name: str | None = None
    attendance_number: str | None = None
    role: UserRole = UserRole.GUEST
    is_premium: bool = True
    is_blacklisted: bool = False


class UserCreate(UserBase):
    password: str | None = None


class UserResponse(UserBase):
    id: str
    email: str
    full_name: str
    class_name: str | None
    attendance_number: str | None
    role: str
    is_premium: bool
    is_blacklisted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema untuk update user (field optional)."""
    full_name: str | None = None
    class_name: str | None = None
    attendance_number: str | None = None
    role: UserRole | None = None
    is_premium: bool | None = None
    is_blacklisted: bool | None = None


class TokenPayload(BaseModel):
    sub: str  # user id
    email: str
    exp: int
    type: str = "access"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetPasswordRequest(BaseModel):
    new_password: str

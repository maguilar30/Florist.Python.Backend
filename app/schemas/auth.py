from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


class UserOut(CamelModel):
    id: str
    email: EmailStr
    full_name: str
    roles: list[str]


class AuthResponse(CamelModel):
    token: str
    expires_at: datetime
    user: UserOut

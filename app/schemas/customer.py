from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class CustomerUpsert(CamelModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=512)
    notes: str | None = None


class CustomerOut(CamelModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    created_at: datetime | None = None

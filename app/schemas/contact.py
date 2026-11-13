from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class ContactMessageCreate(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    message: str = Field(min_length=1, max_length=4000)


class ContactMessageOut(CamelModel):
    id: int
    name: str
    email: EmailStr
    message: str
    read_at: datetime | None = None
    created_at: datetime | None = None


class ContactMessageResponse(CamelModel):
    status: str
    message: str
    contact_message: ContactMessageOut


class ContactMessageUpdate(CamelModel):
    read: bool | None = None

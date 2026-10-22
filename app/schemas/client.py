from datetime import datetime

from pydantic import EmailStr

from app.schemas.base import CamelModel


class ClientOut(CamelModel):
    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    roles: list[str]
    created_at: datetime | None = None

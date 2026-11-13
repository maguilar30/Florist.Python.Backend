from pydantic import Field

from app.schemas.base import CamelModel


class ContactInfoOut(CamelModel):
    heading: str
    description: str
    address: str
    phone: str
    hours: str
    email: str
    instagram_url: str
    facebook_url: str
    whatsapp_url: str


class ContactInfoUpdate(CamelModel):
    heading: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    address: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=50)
    hours: str = Field(default="", max_length=255)
    email: str = Field(default="", max_length=255)
    instagram_url: str = Field(default="", max_length=512)
    facebook_url: str = Field(default="", max_length=512)
    whatsapp_url: str = Field(default="", max_length=512)

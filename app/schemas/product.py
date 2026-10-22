from decimal import Decimal

from pydantic import Field

from app.schemas.base import CamelModel


class ProductOut(CamelModel):
    id: int
    name: str
    description: str
    price: float
    image_url: str | None = None
    category: str | None = None
    in_stock: bool


class ProductUpsert(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    price: Decimal = Field(gt=0)
    image_url: str | None = Field(default=None, max_length=512)
    category: str | None = Field(default=None, max_length=100)
    in_stock: bool = True

from datetime import date
from decimal import Decimal

from pydantic import Field

from app.schemas.base import CamelModel


class DiscountCodeOut(CamelModel):
    id: int
    code: str
    description: str
    percent: float
    max_discount: float
    max_redemptions: int
    redemption_count: int
    expires_at: date


class DiscountCodeUpsert(CamelModel):
    code: str = Field(min_length=3, max_length=40)
    description: str = Field(default="", max_length=500)
    percent: Decimal = Field(gt=0, le=100)
    max_discount: Decimal = Field(gt=0)
    max_redemptions: int = Field(ge=1, le=1_000_000)
    expires_at: date


class DiscountPreviewRequest(CamelModel):
    code: str = Field(min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    subtotal: Decimal = Field(ge=0)


class DiscountPreviewOut(CamelModel):
    code: str
    description: str
    percent: float
    max_discount: float
    discount_amount: float
    remaining: int
    expires_at: date

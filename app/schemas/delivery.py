from decimal import Decimal

from pydantic import Field

from app.schemas.base import CamelModel


class DeliveryFeeOut(CamelModel):
    id: int
    code: str
    label: str
    fee: float
    requires_address: bool
    sort_order: int


class DeliveryFeeUpsertItem(CamelModel):
    id: int | None = None
    label: str = Field(min_length=1, max_length=255)
    fee: Decimal = Field(ge=0)
    requires_address: bool = True


class DeliveryFeeUpdate(CamelModel):
    options: list[DeliveryFeeUpsertItem] = Field(min_length=1)

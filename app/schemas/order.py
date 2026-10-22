from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field

from app.delivery import DELIVERY_OPTIONS
from app.order_status import ORDER_STATUSES
from app.schemas.base import CamelModel

OrderStatus = Literal[
    "payment_pending",
    "paid",
    "preparing",
    "ready_for_pickup",
    "out_for_delivery",
    "delivered",
    "cancelled",
]

DeliveryOption = Literal["pickup", "up_to_2km", "up_to_5km", "over_5km"]


class OrderItemIn(CamelModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)


class OrderRequest(CamelModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    customer_phone: str = Field(min_length=1, max_length=50)
    delivery_address: str | None = Field(default=None, max_length=512)
    delivery_option: DeliveryOption = "pickup"
    notes: str | None = Field(default=None, max_length=2000)
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(CamelModel):
    id: int
    product_id: int | None = None
    name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(CamelModel):
    id: int
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    delivery_address: str | None = None
    notes: str | None = None
    status: str
    delivery_option: str
    subtotal: float
    delivery_fee: float
    total: float
    items: list[OrderItemOut]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrderResponse(CamelModel):
    status: str
    message: str
    order_id: int
    order: OrderOut


class OrderUpdate(CamelModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, min_length=1, max_length=50)
    delivery_address: str | None = Field(default=None, max_length=512)
    notes: str | None = None
    status: OrderStatus | None = None
    delivery_option: DeliveryOption | None = None
    total: Decimal | None = Field(default=None, ge=0)


assert set(ORDER_STATUSES) == set(OrderStatus.__args__)
assert set(DELIVERY_OPTIONS) == set(DeliveryOption.__args__)

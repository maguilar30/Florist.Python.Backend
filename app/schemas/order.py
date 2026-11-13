from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field

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

DeliveryOption = str


class OrderItemIn(CamelModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)


class OrderRequest(CamelModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    customer_phone: str = Field(min_length=1, max_length=50)
    delivery_address: str | None = Field(default=None, max_length=512)
    delivery_option: DeliveryOption = Field(default="pickup", min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)
    discount_code: str | None = Field(default=None, max_length=40)
    loyalty_reward_id: int | None = Field(default=None, ge=1)
    items: list[OrderItemIn] = Field(min_length=1)


class AdminOrderRequest(OrderRequest):
    user_id: str | None = Field(default=None, max_length=36)


class OrderItemOut(CamelModel):
    id: int
    product_id: int | None = None
    name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderEventOut(CamelModel):
    id: int
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    actor_name: str
    actor_role: str
    message: str
    created_at: datetime | None = None


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
    discount_code: str | None = None
    discount_amount: float = 0
    loyalty_reward: str | None = None
    loyalty_discount_amount: float = 0
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
    delivery_option: DeliveryOption | None = Field(default=None, min_length=1, max_length=50)
    total: Decimal | None = Field(default=None, ge=0)


assert set(ORDER_STATUSES) == set(OrderStatus.__args__)

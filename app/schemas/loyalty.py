from decimal import Decimal

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel

LOYALTY_KINDS = ("percent", "free_delivery", "custom")


class LoyaltyRewardUpsert(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    orders_required: int = Field(ge=1, le=10_000)
    kind: str = Field(default="custom")
    percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    max_discount: Decimal = Field(default=Decimal("0"), ge=0)
    active: bool = True


class LoyaltyRewardOut(CamelModel):
    id: int
    name: str
    description: str
    orders_required: int
    kind: str
    percent: float
    max_discount: float
    active: bool


class LoyaltyRewardProgress(LoyaltyRewardOut):
    stars_toward: int
    remaining: int
    redeemed_count: int
    available: bool


class LoyaltyMeOut(CamelModel):
    stars: int
    qualifying_orders: int
    rewards: list[LoyaltyRewardProgress]


class LoyaltyMemberOut(CamelModel):
    user_id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    stars: int
    order_count: int
    total_spent: float

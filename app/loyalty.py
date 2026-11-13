from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.discount import discount_amount_for
from app.errors import problem
from app.models.loyalty import LoyaltyRedemption, LoyaltyReward
from app.models.order import Order
from app.models.user import User
from app.order_status import COMPLETED_ORDER_STATUS
from app.schemas.loyalty import LOYALTY_KINDS

TWOPLACES = Decimal("0.01")


def validate_reward_payload(*, kind: str, percent: Decimal, max_discount: Decimal) -> str:
    normalized = kind.strip().lower()
    if normalized not in LOYALTY_KINDS:
        raise problem(400, "El tipo de recompensa no es válido.")
    if normalized == "percent":
        if percent <= 0 or percent > 100:
            raise problem(400, "El porcentaje de la recompensa debe estar entre 0 y 100.")
        if max_discount <= 0:
            raise problem(400, "El descuento máximo de la recompensa debe ser mayor que cero.")
    return normalized


def star_count(db: Session, company_id: str, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.company_id == company_id,
                Order.user_id == user_id,
                Order.status == COMPLETED_ORDER_STATUS,
            )
        )
        or 0
    )


def redemption_count(db: Session, company_id: str, reward_id: int, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(LoyaltyRedemption)
            .outerjoin(Order, Order.id == LoyaltyRedemption.order_id)
            .where(
                LoyaltyRedemption.company_id == company_id,
                LoyaltyRedemption.loyalty_reward_id == reward_id,
                LoyaltyRedemption.user_id == user_id,
                (LoyaltyRedemption.order_id.is_(None)) | (Order.status != "cancelled"),
            )
        )
        or 0
    )


def get_reward(
    db: Session, company_id: str, reward_id: int, *, for_update: bool = False, require_active: bool = False
) -> LoyaltyReward:
    stmt = select(LoyaltyReward).where(LoyaltyReward.id == reward_id, LoyaltyReward.company_id == company_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if row is None:
        raise problem(404, "La recompensa de fidelidad no existe.")
    if require_active and not row.active:
        raise problem(400, "Esta recompensa de fidelidad no está disponible.")
    return row


def available_redemptions(stars: int, orders_required: int, redeemed: int) -> int:
    if orders_required < 1:
        return 0
    return max(0, stars // orders_required - redeemed)


def assert_reward_available(db: Session, company_id: str, reward: LoyaltyReward, user: User) -> None:
    stars = star_count(db, company_id, user.id)
    used = redemption_count(db, company_id, reward.id, user.id)
    if available_redemptions(stars, reward.orders_required, used) < 1:
        raise problem(
            409,
            f"Aún no tienes suficientes estrellas para {reward.name}. Necesitas {reward.orders_required} pedidos.",
        )


def apply_loyalty(
    db: Session,
    company_id: str,
    reward_id: int | None,
    subtotal: Decimal,
    delivery_fee: Decimal,
    user: User | None,
) -> tuple[LoyaltyReward | None, Decimal, Decimal]:
    if reward_id is None:
        return None, Decimal("0.00"), delivery_fee
    if user is None:
        raise problem(401, "Inicia sesión para canjear tu recompensa de fidelidad.")
    reward = get_reward(db, company_id, reward_id, for_update=True, require_active=True)
    assert_reward_available(db, company_id, reward, user)
    amount = Decimal("0.00")
    fee = delivery_fee
    if reward.kind == "percent":
        amount = discount_amount_for(subtotal, reward.percent, reward.max_discount)
    elif reward.kind == "free_delivery":
        fee = Decimal("0.00")
    return reward, amount, fee

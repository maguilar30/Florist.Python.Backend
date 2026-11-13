from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import problem
from app.models.discount_code import DiscountCode, DiscountRedemption
from app.models.order import Order
from app.models.user import User

TWOPLACES = Decimal("0.01")


def normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = "".join(value.strip().upper().split())
    return code or None


def discount_amount_for(subtotal: Decimal, percent: Decimal, max_discount: Decimal) -> Decimal:
    if subtotal <= 0:
        return Decimal("0.00")
    raw = (subtotal * Decimal(percent) / Decimal("100")).quantize(TWOPLACES)
    capped = min(raw, Decimal(max_discount).quantize(TWOPLACES), subtotal.quantize(TWOPLACES))
    return capped


def redemption_count(db: Session, discount_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(DiscountRedemption)
            .where(DiscountRedemption.discount_code_id == discount_id)
        )
        or 0
    )


def get_discount_code(db: Session, company_id: str, code: str, *, for_update: bool = False) -> DiscountCode:
    normalized = normalize_code(code)
    if not normalized:
        raise problem(400, "Ingresa un código de descuento.")
    stmt = select(DiscountCode).where(DiscountCode.company_id == company_id, DiscountCode.code == normalized)
    if for_update:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if row is None:
        raise problem(404, "El código de descuento no es válido.")
    if row.expires_at < date.today():
        raise problem(400, "Este código de descuento ya venció.")
    return row


def _identity_used(
    db: Session, company_id: str, discount_id: int, email: str, user_id: str | None
) -> bool:
    email = email.strip().lower()
    redemption_filters = [DiscountRedemption.customer_email == email]
    order_filters = [Order.customer_email == email]
    if user_id:
        redemption_filters.append(DiscountRedemption.user_id == user_id)
        order_filters.append(Order.user_id == user_id)
    redemption = db.scalar(
        select(DiscountRedemption.id).where(
            DiscountRedemption.company_id == company_id,
            DiscountRedemption.discount_code_id == discount_id,
            or_(*redemption_filters),
        )
    )
    if redemption is not None:
        return True
    order_match = db.scalar(
        select(Order.id).where(
            Order.company_id == company_id,
            Order.discount_code_id == discount_id,
            or_(*order_filters),
        )
    )
    return order_match is not None


def assert_code_available(
    db: Session, company_id: str, discount: DiscountCode, email: str, user: User | None
) -> None:
    user_id = user.id if user else None
    if _identity_used(db, company_id, discount.id, email, user_id):
        raise problem(409, "Ya usaste este código de descuento. Solo se puede aplicar una vez por cliente.")
    used = redemption_count(db, discount.id)
    if used >= discount.max_redemptions:
        raise problem(409, "Este código ya alcanzó el máximo de usos.")


def apply_discount(
    db: Session,
    company_id: str,
    code: str | None,
    subtotal: Decimal,
    email: str,
    user: User | None,
) -> tuple[DiscountCode | None, Decimal]:
    normalized = normalize_code(code)
    if not normalized:
        return None, Decimal("0.00")
    discount = get_discount_code(db, company_id, normalized, for_update=True)
    assert_code_available(db, company_id, discount, email, user)
    amount = discount_amount_for(subtotal, discount.percent, discount.max_discount)
    return discount, amount

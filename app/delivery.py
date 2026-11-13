import re
import unicodedata
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_fee import DeliveryFee

DEFAULT_DELIVERY_OPTION = "pickup"

DEFAULT_DELIVERY_FEES = [
    {
        "code": "pickup",
        "label": "Recoger en tienda",
        "fee": Decimal("0.00"),
        "requires_address": False,
        "sort_order": 1,
    },
    {
        "code": "up_to_2km",
        "label": "Entrega hasta 2 km",
        "fee": Decimal("5.00"),
        "requires_address": True,
        "sort_order": 2,
    },
    {
        "code": "up_to_5km",
        "label": "Entrega hasta 5 km",
        "fee": Decimal("10.00"),
        "requires_address": True,
        "sort_order": 3,
    },
    {
        "code": "over_5km",
        "label": "Entrega a más de 5 km",
        "fee": Decimal("20.00"),
        "requires_address": True,
        "sort_order": 4,
    },
]

DELIVERY_LABELS = {item["code"]: item["label"] for item in DEFAULT_DELIVERY_FEES}


def slug_code(label: str) -> str:
    normalized = unicodedata.normalize("NFD", label.lower())
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "_", stripped).strip("_")[:40]
    return slug or "delivery"


def unique_code(db: Session, company_id: str, label: str, reserved: set[str] | None = None) -> str:
    taken = set(reserved or ())
    base = slug_code(label)
    code = base
    suffix = 2
    while code in taken or db.scalar(
        select(DeliveryFee.id).where(DeliveryFee.company_id == company_id, DeliveryFee.code == code)
    ):
        code = f"{base}_{suffix}"[:50]
        suffix += 1
    return code


def list_delivery_fees(db: Session, company_id: str) -> list[DeliveryFee]:
    return list(
        db.scalars(
            select(DeliveryFee)
            .where(DeliveryFee.company_id == company_id)
            .order_by(DeliveryFee.sort_order, DeliveryFee.id)
        )
    )


def get_delivery_option(db: Session, company_id: str, code: str) -> DeliveryFee:
    row = db.scalar(
        select(DeliveryFee).where(DeliveryFee.company_id == company_id, DeliveryFee.code == code.strip())
    )
    if row is None:
        raise ValueError(f"Unknown delivery option: {code}")
    return row


def delivery_fee_for(db: Session, company_id: str, code: str) -> Decimal:
    return Decimal(get_delivery_option(db, company_id, code).fee)


def delivery_label_for(db: Session, company_id: str, code: str) -> str:
    try:
        return get_delivery_option(db, company_id, code).label
    except ValueError:
        return DELIVERY_LABELS.get(code, code)

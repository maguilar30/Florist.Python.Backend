import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.delivery import DEFAULT_DELIVERY_FEES
from app.models.company import Company
from app.models.company_contact import CompanyContact
from app.models.delivery_fee import DeliveryFee
from app.models.product import Product

DEFAULT_CONTACT = {
    "heading": "Visítanos o escríbenos",
    "description": (
        "Cuéntanos la ocasión, tu paleta de colores y presupuesto. Respondemos en menos de 24 horas."
    ),
    "address": "Hatillo 3, San José, Costa Rica",
    "phone": "+506 8652-1155",
    "hours": "Lun–Sáb 10:00 – 18:00 · Dom cerrado",
    "email": "info@yadacr.com",
    "instagram_url": "https://instagram.com",
    "facebook_url": "https://facebook.com",
    "whatsapp_url": "https://wa.me/50686521155",
}

CATALOG = [
    {
        "name": "Ramo Clásico",
        "description": "Rosas y verdes en tonos románticos, ideal para aniversarios.",
        "price": Decimal("45.00"),
        "image_url": "https://images.unsplash.com/photo-1561181286-d425a7aae625?w=600&q=80",
        "category": "Ramos",
        "in_stock": True,
    },
    {
        "name": "Jardín Silvestre",
        "description": "Mezcla de campo con texturas naturales y aroma suave.",
        "price": Decimal("38.00"),
        "image_url": "https://images.unsplash.com/photo-1518895949257-7621c3c786d4?w=600&q=80",
        "category": "Ramos",
        "in_stock": True,
    },
    {
        "name": "Elegancia Orquídea",
        "description": "Orquídea en maceta decorativa, regalo duradero y sofisticado.",
        "price": Decimal("62.00"),
        "image_url": "https://images.unsplash.com/photo-1582794543130-2821d68895e2?w=600&q=80",
        "category": "Plantas",
        "in_stock": True,
    },
]


def ensure_default_company(db: Session) -> Company:
    settings = get_settings()
    slug = settings.default_company_slug.strip().lower()
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is not None:
        return company
    company = Company(
        id=str(uuid.uuid4()),
        slug=slug,
        name=settings.default_company_name.strip() or slug,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def ensure_company_contact(db: Session, company: Company) -> CompanyContact:
    row = db.scalar(select(CompanyContact).where(CompanyContact.company_id == company.id))
    if row is not None:
        return row
    row = CompanyContact(company_id=company.id, **DEFAULT_CONTACT)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_delivery_fees(db: Session, company: Company) -> list[DeliveryFee]:
    existing = list(
        db.scalars(
            select(DeliveryFee)
            .where(DeliveryFee.company_id == company.id)
            .order_by(DeliveryFee.sort_order, DeliveryFee.id)
        )
    )
    if existing:
        return existing
    db.add_all([DeliveryFee(company_id=company.id, **item) for item in DEFAULT_DELIVERY_FEES])
    db.commit()
    return list(
        db.scalars(
            select(DeliveryFee)
            .where(DeliveryFee.company_id == company.id)
            .order_by(DeliveryFee.sort_order, DeliveryFee.id)
        )
    )


def seed_products_if_empty(db: Session, company: Company) -> None:
    existing = db.scalar(select(Product.id).where(Product.company_id == company.id).limit(1))
    if existing is not None:
        return
    db.add_all([Product(company_id=company.id, **item) for item in CATALOG])
    db.commit()

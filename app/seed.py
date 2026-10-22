from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product

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


def seed_products_if_empty(db: Session) -> None:
    if db.scalar(select(Product.id).limit(1)) is not None:
        return
    db.add_all([Product(**item) for item in CATALOG])
    db.commit()

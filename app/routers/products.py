from decimal import Decimal

from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import AdminUser, DbSession
from app.errors import problem
from app.models.product import Product
from app.schemas.product import ProductOut, ProductUpsert

router = APIRouter(prefix="/products", tags=["products"])


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _apply(product: Product, payload: ProductUpsert) -> None:
    product.name = payload.name.strip()
    product.description = payload.description.strip()
    product.price = Decimal(payload.price)
    product.image_url = _clean(payload.image_url)
    product.category = _clean(payload.category)
    product.in_stock = payload.in_stock


def _get_product(db: DbSession, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise problem(404, "Not found", "Product not found.")
    return product


@router.get("", response_model=list[ProductOut])
def list_products(db: DbSession) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.name, Product.id)))


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession) -> Product:
    return _get_product(db, product_id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductUpsert, _admin: AdminUser, db: DbSession) -> Product:
    product = Product()
    _apply(product, payload)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpsert,
    _admin: AdminUser,
    db: DbSession,
) -> Product:
    product = _get_product(db, product_id)
    _apply(product, payload)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, _admin: AdminUser, db: DbSession) -> None:
    product = _get_product(db, product_id)
    db.delete(product)
    db.commit()

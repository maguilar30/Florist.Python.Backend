from decimal import Decimal

from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import AdminUser, CurrentCompany, DbSession
from app.errors import problem
from app.inventory import set_stock
from app.models.product import Product
from app.routers.categories import resolve_product_category
from app.schemas.product import ProductOut, ProductUpsert

router = APIRouter(prefix="/products", tags=["products"])


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _apply(product: Product, payload: ProductUpsert, company_id: str, db: DbSession) -> None:
    product.name = payload.name.strip()
    product.description = payload.description.strip()
    product.price = Decimal(payload.price)
    product.image_url = _clean(payload.image_url)
    product.category = resolve_product_category(db, company_id, payload.category)
    set_stock(product, payload.stock_quantity)


def _get_product(db: DbSession, product_id: int, company_id: str) -> Product:
    product = db.scalar(select(Product).where(Product.id == product_id, Product.company_id == company_id))
    if product is None:
        raise problem(404, "Not found", "Product not found.")
    return product


@router.get("", response_model=list[ProductOut])
def list_products(db: DbSession, company: CurrentCompany) -> list[Product]:
    return list(
        db.scalars(select(Product).where(Product.company_id == company.id).order_by(Product.name, Product.id))
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession, company: CurrentCompany) -> Product:
    return _get_product(db, product_id, company.id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductUpsert, _admin: AdminUser, db: DbSession, company: CurrentCompany) -> Product:
    product = Product(company_id=company.id)
    _apply(product, payload, company.id, db)
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
    company: CurrentCompany,
) -> Product:
    product = _get_product(db, product_id, company.id)
    _apply(product, payload, company.id, db)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany) -> None:
    product = _get_product(db, product_id, company.id)
    db.delete(product)
    db.commit()

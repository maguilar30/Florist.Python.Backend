from fastapi import APIRouter, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.deps import AdminUser, CurrentCompany, DbSession
from app.errors import problem
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.schemas.category import ProductCategoryOut, ProductCategoryUpsert
from app.seed import ensure_product_categories

router = APIRouter(prefix="/product-categories", tags=["categories"])


def _out(row: ProductCategory) -> ProductCategoryOut:
    return ProductCategoryOut(id=row.id, name=row.name, sort_order=row.sort_order)


def _clean_name(name: str) -> str:
    return name.strip()


def _get_category(db: DbSession, category_id: int, company_id: str) -> ProductCategory:
    row = db.scalar(
        select(ProductCategory).where(ProductCategory.id == category_id, ProductCategory.company_id == company_id)
    )
    if row is None:
        raise problem(404, "Not found", "Category not found.")
    return row


def list_category_rows(db: DbSession, company_id: str) -> list[ProductCategory]:
    return list(
        db.scalars(
            select(ProductCategory)
            .where(ProductCategory.company_id == company_id)
            .order_by(ProductCategory.sort_order, ProductCategory.name, ProductCategory.id)
        )
    )


def resolve_product_category(db: DbSession, company_id: str, name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    row = db.scalar(
        select(ProductCategory).where(ProductCategory.company_id == company_id, ProductCategory.name == cleaned)
    )
    if row is None:
        raise problem(400, "Invalid category", "Choose a category from the catalog.")
    return row.name


@router.get("", response_model=list[ProductCategoryOut])
def list_categories(db: DbSession, company: CurrentCompany) -> list[ProductCategoryOut]:
    ensure_product_categories(db, company)
    return [_out(row) for row in list_category_rows(db, company.id)]


@router.post("", response_model=ProductCategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: ProductCategoryUpsert, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> ProductCategoryOut:
    name = _clean_name(payload.name)
    next_order = db.scalar(
        select(func.coalesce(func.max(ProductCategory.sort_order), 0)).where(ProductCategory.company_id == company.id)
    )
    row = ProductCategory(company_id=company.id, name=name, sort_order=int(next_order or 0) + 1)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Conflict", "A category with this name already exists.") from None
    db.refresh(row)
    return _out(row)


@router.put("/{category_id}", response_model=ProductCategoryOut)
def update_category(
    category_id: int,
    payload: ProductCategoryUpsert,
    _admin: AdminUser,
    db: DbSession,
    company: CurrentCompany,
) -> ProductCategoryOut:
    row = _get_category(db, category_id, company.id)
    name = _clean_name(payload.name)
    previous = row.name
    row.name = name
    if previous != name:
        db.execute(
            update(Product)
            .where(Product.company_id == company.id, Product.category == previous)
            .values(category=name)
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Conflict", "A category with this name already exists.") from None
    db.refresh(row)
    return _out(row)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany) -> None:
    row = _get_category(db, category_id, company.id)
    db.execute(
        update(Product)
        .where(Product.company_id == company.id, Product.category == row.name)
        .values(category=None)
    )
    db.delete(row)
    db.commit()

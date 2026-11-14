from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import problem
from app.models.order import OrderItem
from app.models.product import Product


def set_stock(product: Product, quantity: int) -> None:
    product.stock_quantity = max(0, int(quantity))
    product.in_stock = product.stock_quantity > 0


def merged_quantities(items: list[tuple[int, int]]) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    for product_id, quantity in items:
        totals[product_id] += quantity
    return dict(totals)


def _locked_products(db: Session, company_id: str, product_ids: list[int]) -> dict[int, Product]:
    if not product_ids:
        return {}
    rows = db.scalars(
        select(Product)
        .where(Product.company_id == company_id, Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
    )
    return {row.id: row for row in rows}


def reserve_stock(db: Session, company_id: str, items: list[tuple[int, int]]) -> dict[int, Product]:
    needed = merged_quantities(items)
    products = _locked_products(db, company_id, list(needed))
    missing = sorted(pid for pid in needed if pid not in products)
    if missing:
        raise problem(400, "Carrito inválido", "Uno o más productos del carrito ya no están disponibles.")
    for product_id, quantity in needed.items():
        product = products[product_id]
        if product.stock_quantity < quantity:
            raise problem(
                409,
                "Inventario insuficiente",
                f"No hay suficientes unidades de {product.name}. Quedan {product.stock_quantity}.",
            )
        set_stock(product, product.stock_quantity - quantity)
    return products


def restore_stock(db: Session, company_id: str, items: list[OrderItem]) -> None:
    needed = merged_quantities(
        [(item.product_id, item.quantity) for item in items if item.product_id is not None]
    )
    products = _locked_products(db, company_id, list(needed))
    for product_id, quantity in needed.items():
        product = products.get(product_id)
        if product is None:
            continue
        set_stock(product, product.stock_quantity + quantity)

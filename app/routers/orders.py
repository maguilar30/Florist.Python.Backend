from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import AdminUser, DbSession
from app.errors import problem
from app.mail import OrderLine, send_order_notification
from app.delivery import DEFAULT_DELIVERY_OPTION, delivery_fee_for
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.order_status import DEFAULT_ORDER_STATUS, ORDER_STATUSES
from app.schemas.order import OrderItemOut, OrderOut, OrderRequest, OrderResponse, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])

SUCCESS_MESSAGE = (
    "Recibimos tu solicitud. Pronto te contactaremos para coordinar el pago."
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _item_out(item: OrderItem) -> OrderItemOut:
    unit = Decimal(item.unit_price)
    line_total = unit * item.quantity
    return OrderItemOut(
        id=item.id,
        product_id=item.product_id,
        name=item.name,
        quantity=item.quantity,
        unit_price=float(unit),
        line_total=float(line_total),
    )


def _order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        customer_phone=order.customer_phone,
        delivery_address=order.delivery_address,
        notes=order.notes,
        status=order.status,
        delivery_option=order.delivery_option,
        subtotal=float(order.subtotal),
        delivery_fee=float(order.delivery_fee),
        total=float(order.total),
        items=[_item_out(item) for item in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _get_order(db: DbSession, order_id: int) -> Order:
    order = db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    if order is None:
        raise problem(404, "Not found", "Order not found.")
    return order


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def request_order(payload: OrderRequest, db: DbSession) -> OrderResponse:
    product_ids = [item.product_id for item in payload.items]
    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids)))
    }
    missing = sorted({pid for pid in product_ids if pid not in products})
    if missing:
        raise problem(400, "Invalid cart", "One or more products in the cart are no longer available.")

    lines = [
        OrderLine(
            name=products[item.product_id].name,
            quantity=item.quantity,
            unit_price=products[item.product_id].price,
            in_stock=products[item.product_id].in_stock,
        )
        for item in payload.items
    ]
    subtotal = sum((line.line_total for line in lines), Decimal("0"))
    try:
        fee = delivery_fee_for(payload.delivery_option)
    except ValueError:
        raise problem(400, "Invalid delivery", "Unknown delivery option.") from None
    address = _clean(payload.delivery_address)
    if payload.delivery_option != "pickup" and not address:
        raise problem(400, "Address required", "A delivery address is required for home delivery.")

    order = Order(
        customer_name=payload.customer_name.strip(),
        customer_email=str(payload.customer_email).lower(),
        customer_phone=payload.customer_phone.strip(),
        delivery_address=address,
        notes=_clean(payload.notes),
        status=DEFAULT_ORDER_STATUS,
        delivery_option=payload.delivery_option or DEFAULT_DELIVERY_OPTION,
        subtotal=subtotal,
        delivery_fee=fee,
        total=subtotal + fee,
        items=[
            OrderItem(
                product_id=item.product_id,
                name=products[item.product_id].name,
                quantity=item.quantity,
                unit_price=products[item.product_id].price,
            )
            for item in payload.items
        ],
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    order = _get_order(db, order.id)

    try:
        send_order_notification(
            order_id=order.id,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            customer_phone=order.customer_phone,
            delivery_address=order.delivery_address,
            notes=order.notes,
            delivery_option=order.delivery_option,
            delivery_fee=order.delivery_fee,
            lines=lines,
        )
    except HTTPException:
        # The order is already stored; email is a notification only.
        pass

    return OrderResponse(
        status="ok",
        message=SUCCESS_MESSAGE,
        order_id=order.id,
        order=_order_out(order),
    )


@router.get("", response_model=list[OrderOut])
def list_orders(_admin: AdminUser, db: DbSession) -> list[OrderOut]:
    orders = db.scalars(
        select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [_order_out(order) for order in orders]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, _admin: AdminUser, db: DbSession) -> OrderOut:
    return _order_out(_get_order(db, order_id))


@router.put("/{order_id}", response_model=OrderOut)
def update_order(order_id: int, payload: OrderUpdate, _admin: AdminUser, db: DbSession) -> OrderOut:
    order = _get_order(db, order_id)
    if payload.customer_name is not None:
        order.customer_name = payload.customer_name.strip()
    if payload.customer_email is not None:
        order.customer_email = str(payload.customer_email).lower()
    if payload.customer_phone is not None:
        order.customer_phone = payload.customer_phone.strip()
    if payload.delivery_address is not None:
        order.delivery_address = _clean(payload.delivery_address)
    if payload.notes is not None:
        order.notes = _clean(payload.notes)
    if payload.status is not None:
        if payload.status not in ORDER_STATUSES:
            raise problem(400, "Invalid status", "Unknown order status.")
        order.status = payload.status
    if payload.delivery_option is not None:
        try:
            order.delivery_fee = delivery_fee_for(payload.delivery_option)
        except ValueError:
            raise problem(400, "Invalid delivery", "Unknown delivery option.") from None
        order.delivery_option = payload.delivery_option
        if payload.delivery_option != "pickup" and not _clean(order.delivery_address):
            raise problem(400, "Address required", "A delivery address is required for home delivery.")
        order.total = Decimal(order.subtotal) + order.delivery_fee
    if payload.total is not None:
        order.total = Decimal(payload.total)
    db.commit()
    return _order_out(_get_order(db, order.id))

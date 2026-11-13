from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import AdminUser, CurrentCompany, CurrentUser, DbSession, OptionalUser
from app.discount import apply_discount
from app.errors import problem
from app.loyalty import apply_loyalty
from app.mail import OrderLine, send_order_notification, send_order_status_email
from app.delivery import DEFAULT_DELIVERY_OPTION, delivery_label_for, get_delivery_option
from app.models.discount_code import DiscountRedemption
from app.models.loyalty import LoyaltyRedemption
from app.models.order import Order, OrderEvent, OrderItem
from app.models.product import Product
from app.models.user import User
from app.order_history import EVENT_CREATED, record_order_event, record_status_history
from app.order_status import DEFAULT_ORDER_STATUS, ORDER_STATUSES
from app.schemas.order import (
    AdminOrderRequest,
    OrderEventOut,
    OrderItemOut,
    OrderOut,
    OrderRequest,
    OrderResponse,
    OrderUpdate,
)

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
        discount_code=order.discount_code,
        discount_amount=float(order.discount_amount or 0),
        loyalty_reward=order.loyalty_reward,
        loyalty_discount_amount=float(order.loyalty_discount_amount or 0),
        total=float(order.total),
        items=[_item_out(item) for item in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _event_out(event: OrderEvent) -> OrderEventOut:
    return OrderEventOut(
        id=event.id,
        event_type=event.event_type,
        from_status=event.from_status,
        to_status=event.to_status,
        actor_name=event.actor_name,
        actor_role=event.actor_role,
        message=event.message,
        created_at=event.created_at,
    )


def _list_events(db: DbSession, order_id: int, company_id: str) -> list[OrderEventOut]:
    events = db.scalars(
        select(OrderEvent)
        .where(OrderEvent.order_id == order_id, OrderEvent.company_id == company_id)
        .order_by(OrderEvent.created_at.asc(), OrderEvent.id.asc())
    )
    return [_event_out(event) for event in events]


def _orders_for_account(user: User, company_id: str):
    return and_(
        Order.company_id == company_id,
        or_(Order.user_id == user.id, Order.customer_email == user.email.lower()),
    )


def _get_order(db: DbSession, order_id: int, company_id: str) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.company_id == company_id)
    )
    if order is None:
        raise problem(404, "Not found", "Order not found.")
    return order


def _place_order(
    payload: OrderRequest,
    db: DbSession,
    company_id: str,
    *,
    owner: User | None,
    actor: User | None,
    created_message: str | None = None,
) -> OrderResponse:
    product_ids = [item.product_id for item in payload.items]
    products = {
        product.id: product
        for product in db.scalars(
            select(Product).where(Product.id.in_(product_ids), Product.company_id == company_id)
        )
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
        delivery = get_delivery_option(db, company_id, payload.delivery_option)
    except ValueError:
        raise problem(400, "Invalid delivery", "Unknown delivery option.") from None
    fee = delivery.fee
    address = _clean(payload.delivery_address)
    if delivery.requires_address and not address:
        raise problem(400, "Address required", "A delivery address is required for home delivery.")
    email = str(payload.customer_email).lower()
    if payload.discount_code and payload.loyalty_reward_id:
        raise problem(400, "Usa el código de descuento o la recompensa de fidelidad, no ambos.")
    discount, discount_amount = apply_discount(
        db, company_id, payload.discount_code, subtotal, email, owner
    )
    loyalty, loyalty_discount, fee = apply_loyalty(
        db, company_id, payload.loyalty_reward_id, subtotal, fee, owner
    )

    order = Order(
        company_id=company_id,
        user_id=owner.id if owner else None,
        customer_name=payload.customer_name.strip(),
        customer_email=email,
        customer_phone=payload.customer_phone.strip(),
        delivery_address=address,
        notes=_clean(payload.notes),
        status=DEFAULT_ORDER_STATUS,
        delivery_option=payload.delivery_option or DEFAULT_DELIVERY_OPTION,
        subtotal=subtotal,
        delivery_fee=fee,
        discount_code_id=discount.id if discount else None,
        discount_code=discount.code if discount else None,
        discount_amount=discount_amount,
        loyalty_reward_id=loyalty.id if loyalty else None,
        loyalty_reward=loyalty.name if loyalty else None,
        loyalty_discount_amount=loyalty_discount,
        total=subtotal - discount_amount - loyalty_discount + fee,
        items=[
            OrderItem(
                company_id=company_id,
                product_id=item.product_id,
                name=products[item.product_id].name,
                quantity=item.quantity,
                unit_price=products[item.product_id].price,
            )
            for item in payload.items
        ],
    )
    db.add(order)
    db.flush()
    if discount is not None:
        db.add(
            DiscountRedemption(
                company_id=company_id,
                discount_code_id=discount.id,
                customer_email=email,
                user_id=owner.id if owner else None,
                order_id=order.id,
            )
        )
    if loyalty is not None and owner is not None:
        db.add(
            LoyaltyRedemption(
                company_id=company_id,
                loyalty_reward_id=loyalty.id,
                user_id=owner.id,
                order_id=order.id,
            )
        )
    record_order_event(
        db,
        company_id=company_id,
        order_id=order.id,
        event_type=EVENT_CREATED,
        actor=actor,
        actor_name=actor.full_name if actor else order.customer_name,
        to_status=order.status,
        message=created_message,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Ya usaste este código de descuento. Solo se puede aplicar una vez por cliente.") from None
    order = _get_order(db, order.id, company_id)

    try:
        send_order_notification(
            order_id=order.id,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            customer_phone=order.customer_phone,
            delivery_address=order.delivery_address,
            notes=order.notes,
            delivery_option=order.delivery_option,
            delivery_label=delivery_label_for(db, company_id, order.delivery_option),
            delivery_fee=order.delivery_fee,
            discount_code=order.discount_code,
            discount_amount=order.discount_amount,
            loyalty_reward=order.loyalty_reward,
            loyalty_discount_amount=order.loyalty_discount_amount,
            lines=lines,
        )
    except HTTPException:
        pass

    return OrderResponse(
        status="ok",
        message=SUCCESS_MESSAGE,
        order_id=order.id,
        order=_order_out(order),
    )


def _user_for_company(db: DbSession, company_id: str, user_id: str | None, email: str) -> User | None:
    if user_id:
        owner = db.scalar(select(User).where(User.id == user_id, User.company_id == company_id))
        if owner is None:
            raise problem(404, "Not found", "Customer account not found.")
        return owner
    return db.scalar(select(User).where(User.company_id == company_id, User.email == email.lower()))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def request_order(
    payload: OrderRequest, db: DbSession, user: OptionalUser, company: CurrentCompany
) -> OrderResponse:
    return _place_order(payload, db, company.id, owner=user, actor=user)


@router.post("/admin", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_admin_order(
    payload: AdminOrderRequest, admin: AdminUser, db: DbSession, company: CurrentCompany
) -> OrderResponse:
    owner = _user_for_company(db, company.id, payload.user_id, str(payload.customer_email))
    return _place_order(
        payload,
        db,
        company.id,
        owner=owner,
        actor=admin,
        created_message="Pedido creado por un administrador en nombre del cliente.",
    )


@router.get("/mine", response_model=list[OrderOut])
def list_my_orders(user: CurrentUser, db: DbSession, company: CurrentCompany) -> list[OrderOut]:
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(_orders_for_account(user, company.id))
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [_order_out(order) for order in orders]


@router.get("/mine/{order_id}", response_model=OrderOut)
def get_my_order(order_id: int, user: CurrentUser, db: DbSession, company: CurrentCompany) -> OrderOut:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, _orders_for_account(user, company.id))
    )
    if order is None:
        raise problem(404, "Not found", "Order not found.")
    return _order_out(order)


@router.get("/mine/{order_id}/history", response_model=list[OrderEventOut])
def get_my_order_history(
    order_id: int, user: CurrentUser, db: DbSession, company: CurrentCompany
) -> list[OrderEventOut]:
    order = db.scalar(select(Order).where(Order.id == order_id, _orders_for_account(user, company.id)))
    if order is None:
        raise problem(404, "Not found", "Order not found.")
    return _list_events(db, order.id, company.id)


@router.get("", response_model=list[OrderOut])
def list_orders(_admin: AdminUser, db: DbSession, company: CurrentCompany) -> list[OrderOut]:
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.company_id == company.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [_order_out(order) for order in orders]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany) -> OrderOut:
    return _order_out(_get_order(db, order_id, company.id))


@router.get("/{order_id}/history", response_model=list[OrderEventOut])
def get_order_history(
    order_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> list[OrderEventOut]:
    _get_order(db, order_id, company.id)
    return _list_events(db, order_id, company.id)


@router.put("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int, payload: OrderUpdate, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> OrderOut:
    order = _get_order(db, order_id, company.id)
    previous_status = order.status
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
            delivery = get_delivery_option(db, company.id, payload.delivery_option)
        except ValueError:
            raise problem(400, "Invalid delivery", "Unknown delivery option.") from None
        order.delivery_fee = delivery.fee
        order.delivery_option = delivery.code
        if delivery.requires_address and not _clean(order.delivery_address):
            raise problem(400, "Address required", "A delivery address is required for home delivery.")
        order.total = (
            Decimal(order.subtotal)
            - Decimal(order.discount_amount or 0)
            - Decimal(order.loyalty_discount_amount or 0)
            + order.delivery_fee
        )
    if payload.total is not None:
        order.total = Decimal(payload.total)
    if payload.status is not None and order.status != previous_status:
        record_status_history(
            db,
            company_id=company.id,
            order_id=order.id,
            previous_status=previous_status,
            new_status=order.status,
            actor=_admin,
            actor_name=_admin.full_name,
        )
    db.commit()
    order = _get_order(db, order.id, company.id)
    if payload.status is not None and order.status != previous_status:
        try:
            send_order_status_email(
                order_id=order.id,
                customer_name=order.customer_name,
                customer_email=order.customer_email,
                status=order.status,
                total=Decimal(order.total),
            )
        except HTTPException:
            # Status is already persisted; mail is a notification only.
            pass
    return _order_out(order)

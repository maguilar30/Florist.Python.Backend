from sqlalchemy.orm import Session

from app.models.order import OrderEvent
from app.models.user import User
from app.order_status import COMPLETED_ORDER_STATUS, order_status_label

EVENT_CREATED = "created"
EVENT_STATUS_CHANGED = "status_changed"
EVENT_COMPLETED = "completed"


def actor_role_for(user: User | None) -> str:
    if user is None:
        return "guest"
    return "admin" if user.role.lower() == "admin" else "customer"


def record_order_event(
    db: Session,
    *,
    company_id: str,
    order_id: int,
    event_type: str,
    actor: User | None,
    actor_name: str,
    from_status: str | None = None,
    to_status: str | None = None,
    message: str | None = None,
) -> OrderEvent:
    event = OrderEvent(
        company_id=company_id,
        order_id=order_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor.id if actor else None,
        actor_name=actor_name.strip() or "Sistema",
        actor_role=actor_role_for(actor),
        message=message or _default_message(event_type, from_status, to_status),
    )
    db.add(event)
    return event


def record_status_history(
    db: Session,
    *,
    company_id: str,
    order_id: int,
    previous_status: str,
    new_status: str,
    actor: User | None,
    actor_name: str,
) -> None:
    record_order_event(
        db,
        company_id=company_id,
        order_id=order_id,
        event_type=EVENT_STATUS_CHANGED,
        actor=actor,
        actor_name=actor_name,
        from_status=previous_status,
        to_status=new_status,
    )
    if new_status == COMPLETED_ORDER_STATUS and previous_status != COMPLETED_ORDER_STATUS:
        record_order_event(
            db,
            company_id=company_id,
            order_id=order_id,
            event_type=EVENT_COMPLETED,
            actor=actor,
            actor_name=actor_name,
            from_status=previous_status,
            to_status=new_status,
        )


def _default_message(event_type: str, from_status: str | None, to_status: str | None) -> str:
    if event_type == EVENT_CREATED:
        label = order_status_label(to_status or "payment_pending")
        return f"Pedido creado con estado {label}."
    if event_type == EVENT_COMPLETED:
        return "Pedido completado (entregado)."
    if event_type == EVENT_STATUS_CHANGED:
        previous = order_status_label(from_status or "")
        current = order_status_label(to_status or "")
        return f"Estado actualizado de {previous} a {current}."
    return "Evento de pedido."

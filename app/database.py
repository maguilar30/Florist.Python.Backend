from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_schema(bind: Engine) -> None:
    inspector = inspect(bind)
    if "orders" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("orders")}
    statements: list[str] = []
    if "subtotal" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0")
        statements.append("UPDATE orders SET subtotal = total")
    if "delivery_option" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN delivery_option VARCHAR(50) NOT NULL DEFAULT 'pickup'")
    if "delivery_fee" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN delivery_fee NUMERIC(10, 2) NOT NULL DEFAULT 0")
    if "user_id" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN user_id VARCHAR(36) NULL")
        statements.append("CREATE INDEX ix_orders_user_id ON orders (user_id)")
    if statements:
        with bind.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    _backfill_order_events(bind)


def _backfill_order_events(bind: Engine) -> None:
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "orders" not in tables or "order_events" not in tables:
        return
    with bind.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO order_events (
                    order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.id,
                    'created',
                    NULL,
                    'payment_pending',
                    o.customer_name,
                    'customer',
                    'Pedido creado con estado Pago pendiente.',
                    o.created_at
                FROM orders o
                WHERE NOT EXISTS (
                    SELECT 1 FROM order_events e
                    WHERE e.order_id = o.id AND e.event_type = 'created'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO order_events (
                    order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.id,
                    'status_changed',
                    'payment_pending',
                    o.status,
                    o.customer_name,
                    'admin',
                    CONCAT('Estado actualizado de Pago pendiente a ', o.status, '.'),
                    o.updated_at
                FROM orders o
                WHERE o.status <> 'payment_pending'
                  AND NOT EXISTS (
                    SELECT 1 FROM order_events e
                    WHERE e.order_id = o.id AND e.event_type = 'status_changed'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO order_events (
                    order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.id,
                    'completed',
                    NULL,
                    'delivered',
                    o.customer_name,
                    'admin',
                    'Pedido completado (entregado).',
                    o.updated_at
                FROM orders o
                WHERE o.status = 'delivered'
                  AND NOT EXISTS (
                    SELECT 1 FROM order_events e
                    WHERE e.order_id = o.id AND e.event_type = 'completed'
                )
                """
            )
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

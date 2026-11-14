import uuid
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
    if "discount_code_id" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN discount_code_id INT NULL")
        statements.append("CREATE INDEX ix_orders_discount_code_id ON orders (discount_code_id)")
    if "discount_code" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN discount_code VARCHAR(40) NULL")
    if "discount_amount" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0")
    if "loyalty_reward_id" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN loyalty_reward_id INT NULL")
        statements.append("CREATE INDEX ix_orders_loyalty_reward_id ON orders (loyalty_reward_id)")
    if "loyalty_reward" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN loyalty_reward VARCHAR(120) NULL")
    if "loyalty_discount_amount" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN loyalty_discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0")
    if statements:
        with bind.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    _ensure_company_tenancy(bind)
    _ensure_contact_phone(bind)
    _ensure_discount_max_redemptions(bind)
    _ensure_product_stock_quantity(bind)
    _backfill_order_events(bind)


def _ensure_product_stock_quantity(bind: Engine) -> None:
    inspector = inspect(bind)
    if "products" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("products")}
    if "stock_quantity" in columns:
        return
    with bind.begin() as connection:
        connection.execute(
            text("ALTER TABLE products ADD COLUMN stock_quantity INT NOT NULL DEFAULT 0")
        )
        if "in_stock" in columns:
            connection.execute(
                text("UPDATE products SET stock_quantity = 10 WHERE in_stock = 1 AND stock_quantity = 0")
            )


def _ensure_discount_max_redemptions(bind: Engine) -> None:
    inspector = inspect(bind)
    if "discount_codes" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("discount_codes")}
    if "max_redemptions" in columns:
        return
    with bind.begin() as connection:
        connection.execute(
            text("ALTER TABLE discount_codes ADD COLUMN max_redemptions INT NOT NULL DEFAULT 100")
        )


def _ensure_contact_phone(bind: Engine) -> None:
    inspector = inspect(bind)
    if "contact_messages" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("contact_messages")}
    if "phone" in columns:
        return
    with bind.begin() as connection:
        connection.execute(
            text("ALTER TABLE contact_messages ADD COLUMN phone VARCHAR(50) NOT NULL DEFAULT ''")
        )


TENANT_TABLES = (
    "users",
    "products",
    "customers",
    "orders",
    "order_items",
    "order_events",
    "password_reset_tokens",
    "contact_messages",
    "company_contacts",
    "delivery_fees",
    "product_categories",
    "discount_codes",
    "discount_code_redemptions",
    "loyalty_rewards",
    "loyalty_redemptions",
)


def _ensure_company_tenancy(bind: Engine) -> None:
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "companies" not in tables:
        return

    settings = get_settings()
    slug = settings.default_company_slug.strip().lower()
    with bind.begin() as connection:
        row = connection.execute(text("SELECT id FROM companies WHERE slug = :slug"), {"slug": slug}).first()
        if row is None:
            company_id = str(uuid.uuid4())
            connection.execute(
                text("INSERT INTO companies (id, slug, name) VALUES (:id, :slug, :name)"),
                {"id": company_id, "slug": slug, "name": settings.default_company_name.strip() or slug},
            )
        else:
            company_id = str(row[0])

        for table in TENANT_TABLES:
            if table not in tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "company_id" in columns:
                continue
            connection.execute(text(f"ALTER TABLE `{table}` ADD COLUMN company_id VARCHAR(36) NULL"))
            connection.execute(
                text(f"UPDATE `{table}` SET company_id = :company_id WHERE company_id IS NULL"),
                {"company_id": company_id},
            )
            connection.execute(text(f"ALTER TABLE `{table}` MODIFY company_id VARCHAR(36) NOT NULL"))
            connection.execute(text(f"CREATE INDEX ix_{table}_company_id ON `{table}` (company_id)"))

    _ensure_company_email_uniques(bind)


def _ensure_company_email_uniques(bind: Engine) -> None:
    inspector = inspect(bind)
    statements: list[str] = []
    for table, constraint in (("users", "uq_users_company_email"), ("customers", "uq_customers_company_email")):
        if table not in inspector.get_table_names():
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "company_id" not in columns:
            continue
        uniques = inspector.get_unique_constraints(table)
        indexes = inspector.get_indexes(table)
        names = {item.get("name") for item in uniques} | {item.get("name") for item in indexes}
        for unique in uniques:
            cols = list(unique.get("column_names") or [])
            name = unique.get("name")
            if cols == ["email"] and name:
                statements.append(f"ALTER TABLE `{table}` DROP INDEX `{name}`")
                names.discard(name)
        for index in indexes:
            cols = list(index.get("column_names") or [])
            name = index.get("name")
            if index.get("unique") and cols == ["email"] and name:
                statements.append(f"ALTER TABLE `{table}` DROP INDEX `{name}`")
                names.discard(name)
        if constraint not in names:
            statements.append(f"ALTER TABLE `{table}` ADD UNIQUE INDEX `{constraint}` (company_id, email)")
    if not statements:
        return
    with bind.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
                    company_id, order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.company_id,
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
                    company_id, order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.company_id,
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
                    company_id, order_id, event_type, from_status, to_status,
                    actor_name, actor_role, message, created_at
                )
                SELECT
                    o.company_id,
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

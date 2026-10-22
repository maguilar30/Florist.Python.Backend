from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminUser, DbSession
from app.errors import problem
from app.models.customer import Customer
from app.schemas.customer import CustomerOut, CustomerUpsert

router = APIRouter(prefix="/customers", tags=["customers"])


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _apply(customer: Customer, payload: CustomerUpsert) -> None:
    customer.full_name = payload.full_name.strip()
    customer.email = str(payload.email).lower()
    customer.phone = _clean(payload.phone)
    customer.address = _clean(payload.address)
    customer.notes = _clean(payload.notes)


def _get_customer(db: DbSession, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise problem(404, "Not found", "Customer not found.")
    return customer


@router.get("", response_model=list[CustomerOut])
def list_customers(_admin: AdminUser, db: DbSession) -> list[Customer]:
    return list(db.scalars(select(Customer).order_by(Customer.full_name, Customer.id)))


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, _admin: AdminUser, db: DbSession) -> Customer:
    return _get_customer(db, customer_id)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerUpsert, _admin: AdminUser, db: DbSession) -> Customer:
    customer = Customer()
    _apply(customer, payload)
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Conflict", "A customer with this email already exists.") from None
    db.refresh(customer)
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerUpsert,
    _admin: AdminUser,
    db: DbSession,
) -> Customer:
    customer = _get_customer(db, customer_id)
    _apply(customer, payload)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Conflict", "A customer with this email already exists.") from None
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, _admin: AdminUser, db: DbSession) -> None:
    customer = _get_customer(db, customer_id)
    db.delete(customer)
    db.commit()

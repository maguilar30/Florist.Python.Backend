from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import AdminUser, DbSession
from app.errors import problem
from app.models.user import User
from app.schemas.client import ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


def _to_out(user: User) -> ClientOut:
    return ClientOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        roles=[user.role],
        created_at=user.created_at,
    )


def _customer_accounts():
    return select(User).where(func.lower(User.role) == "customer")


@router.get("", response_model=list[ClientOut])
def list_clients(_admin: AdminUser, db: DbSession) -> list[ClientOut]:
    users = db.scalars(_customer_accounts().order_by(User.full_name, User.email))
    return [_to_out(user) for user in users]


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, _admin: AdminUser, db: DbSession) -> ClientOut:
    user = db.scalar(_customer_accounts().where(User.id == client_id))
    if user is None:
        raise problem(404, "Not found", "Client account not found.")
    return _to_out(user)

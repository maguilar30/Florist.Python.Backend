from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.errors import problem
from app.models.customer import Customer
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.security import create_access_token, hash_password, user_to_out, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    token, expires_at = create_access_token(user)
    return AuthResponse(token=token, expires_at=expires_at, user=user_to_out(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise problem(401, "Invalid credentials", "Email or password is incorrect.")
    return _auth_response(user)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise problem(409, "Conflict", "An account with this email already exists.")

    full_name = payload.full_name.strip()
    phone = payload.phone.strip() if payload.phone else None
    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(payload.password),
        role="Customer",
    )
    db.add(user)

    existing_customer = db.scalar(select(Customer).where(Customer.email == email))
    if existing_customer is None:
        db.add(Customer(full_name=full_name, email=email, phone=phone))
    else:
        existing_customer.full_name = full_name
        if phone:
            existing_customer.phone = phone

    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> UserOut:
    return user_to_out(current_user)

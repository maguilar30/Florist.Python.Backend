import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from app.config import get_settings
from app.deps import CurrentCompany, CurrentUser, DbSession
from app.errors import problem
from app.mail import send_password_reset_email
from app.models.customer import Customer
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.security import create_access_token, hash_password, hash_reset_token, user_to_out, verify_password

FORGOT_PASSWORD_MESSAGE = (
    "Si el correo está registrado, te enviaremos un enlace para restablecer la contraseña."
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    token, expires_at = create_access_token(user)
    return AuthResponse(token=token, expires_at=expires_at, user=user_to_out(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession, company: CurrentCompany) -> AuthResponse:
    user = db.scalar(
        select(User).where(User.email == payload.email.lower(), User.company_id == company.id)
    )
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise problem(401, "Invalid credentials", "Email or password is incorrect.")
    return _auth_response(user)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession, company: CurrentCompany) -> AuthResponse:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email, User.company_id == company.id))
    if existing:
        raise problem(409, "Conflict", "An account with this email already exists.")

    full_name = payload.full_name.strip()
    phone = payload.phone.strip() if payload.phone else None
    user = User(
        company_id=company.id,
        email=email,
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(payload.password),
        role="Customer",
    )
    db.add(user)

    existing_customer = db.scalar(
        select(Customer).where(Customer.email == email, Customer.company_id == company.id)
    )
    if existing_customer is None:
        db.add(Customer(company_id=company.id, full_name=full_name, email=email, phone=phone))
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


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: DbSession, company: CurrentCompany) -> MessageResponse:
    settings = get_settings()
    if not settings.smtp_host and not settings.debug:
        raise problem(503, "Mail not configured", "Email cannot be sent until SMTP is configured.")

    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email, User.company_id == company.id))
    if user is not None:
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_expire_minutes)
        db.add(
            PasswordResetToken(
                company_id=company.id,
                user_id=user.id,
                token_hash=hash_reset_token(raw_token),
                expires_at=expires_at,
            )
        )
        db.commit()
        origin = settings.frontend_url.rstrip("/")
        reset_url = f"{origin}/restablecer-contrasena?token={raw_token}"
        try:
            send_password_reset_email(to_addr=user.email, full_name=user.full_name, reset_url=reset_url)
        except HTTPException:
            pass
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: DbSession, company: CurrentCompany) -> MessageResponse:
    token_hash = hash_reset_token(payload.token.strip())
    record = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.company_id == company.id,
        )
    )
    now = datetime.now(UTC)
    expires_at = record.expires_at if record else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if record is None or record.used_at is not None or expires_at is None or expires_at <= now:
        raise problem(400, "Invalid token", "The reset link is invalid or has expired.")

    user = db.get(User, record.user_id)
    if user is None or user.company_id != company.id:
        raise problem(400, "Invalid token", "The reset link is invalid or has expired.")

    user.hashed_password = hash_password(payload.password)
    record.used_at = now
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != record.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()
    return MessageResponse(message="Tu contraseña se actualizó. Ya puedes iniciar sesión.")

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine, ensure_schema
from app.errors import http_exception_handler, validation_exception_handler
from app.models import Company, CompanyContact, ContactMessage, DeliveryFee, Order, OrderEvent, PasswordResetToken, User
from app.routers.auth import router as auth_router
from app.routers.clients import router as clients_router
from app.routers.contact import router as contact_router
from app.routers.contact_info import router as contact_info_router
from app.routers.customers import router as customers_router
from app.routers.delivery import router as delivery_router
from app.routers.orders import router as orders_router
from app.routers.products import router as products_router
from app.security import hash_password
from app.seed import ensure_company_contact, ensure_default_company, ensure_delivery_fees, seed_products_if_empty

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)

    with SessionLocal() as db:
        company = ensure_default_company(db)
        if db.scalar(select(User.id).where(User.company_id == company.id).limit(1)) is None:
            db.add(
                User(
                    company_id=company.id,
                    email=settings.admin_email.lower(),
                    full_name=settings.admin_full_name,
                    hashed_password=hash_password(settings.admin_password),
                    role="Admin",
                )
            )
            db.commit()
        seed_products_if_empty(db, company)
        ensure_company_contact(db, company)
        ensure_delivery_fees(db, company)

    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(customers_router, prefix=settings.api_prefix)
app.include_router(clients_router, prefix=settings.api_prefix)
app.include_router(products_router, prefix=settings.api_prefix)
app.include_router(orders_router, prefix=settings.api_prefix)
app.include_router(contact_router, prefix=settings.api_prefix)
app.include_router(contact_info_router, prefix=settings.api_prefix)
app.include_router(delivery_router, prefix=settings.api_prefix)


@app.get("/", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "name": settings.app_name}
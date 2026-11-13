from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminUser, CurrentCompany, DbSession, OptionalUser
from app.discount import apply_discount, normalize_code, redemption_count
from app.errors import problem
from app.models.discount_code import DiscountCode
from app.schemas.discount import DiscountCodeOut, DiscountCodeUpsert, DiscountPreviewOut, DiscountPreviewRequest

router = APIRouter(prefix="/discount-codes", tags=["discounts"])


def _out(row: DiscountCode, used: int | None = None, db: DbSession | None = None) -> DiscountCodeOut:
    count = used if used is not None else redemption_count(db, row.id) if db is not None else 0
    return DiscountCodeOut(
        id=row.id,
        code=row.code,
        description=row.description,
        percent=float(row.percent),
        max_discount=float(row.max_discount),
        max_redemptions=row.max_redemptions,
        redemption_count=count,
        expires_at=row.expires_at,
    )


def _get(db: DbSession, discount_id: int, company_id: str) -> DiscountCode:
    row = db.scalar(
        select(DiscountCode).where(DiscountCode.id == discount_id, DiscountCode.company_id == company_id)
    )
    if row is None:
        raise problem(404, "Not found", "Discount code not found.")
    return row


@router.get("", response_model=list[DiscountCodeOut])
def list_discount_codes(_admin: AdminUser, db: DbSession, company: CurrentCompany) -> list[DiscountCodeOut]:
    rows = db.scalars(
        select(DiscountCode)
        .where(DiscountCode.company_id == company.id)
        .order_by(DiscountCode.expires_at.desc(), DiscountCode.code)
    )
    return [_out(row, db=db) for row in rows]


@router.post("/preview", response_model=DiscountPreviewOut)
def preview_discount(
    payload: DiscountPreviewRequest, db: DbSession, user: OptionalUser, company: CurrentCompany
) -> DiscountPreviewOut:
    email = (payload.email or (user.email if user else "")).strip()
    if not email:
        raise problem(400, "Indica tu correo para aplicar el código.")
    discount, amount = apply_discount(db, company.id, payload.code, payload.subtotal, email, user)
    if discount is None:
        raise problem(400, "Ingresa un código de descuento.")
    return DiscountPreviewOut(
        code=discount.code,
        description=discount.description,
        percent=float(discount.percent),
        max_discount=float(discount.max_discount),
        discount_amount=float(amount),
        remaining=max(0, discount.max_redemptions - redemption_count(db, discount.id)),
        expires_at=discount.expires_at,
    )


@router.post("", response_model=DiscountCodeOut, status_code=status.HTTP_201_CREATED)
def create_discount_code(
    payload: DiscountCodeUpsert, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> DiscountCodeOut:
    code = normalize_code(payload.code)
    if not code:
        raise problem(400, "Ingresa un código de descuento.")
    row = DiscountCode(
        company_id=company.id,
        code=code,
        description=payload.description.strip(),
        percent=payload.percent,
        max_discount=payload.max_discount,
        max_redemptions=payload.max_redemptions,
        expires_at=payload.expires_at,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Ya existe un código con ese nombre.") from None
    db.refresh(row)
    return _out(row, db=db)


@router.put("/{discount_id}", response_model=DiscountCodeOut)
def update_discount_code(
    discount_id: int,
    payload: DiscountCodeUpsert,
    _admin: AdminUser,
    db: DbSession,
    company: CurrentCompany,
) -> DiscountCodeOut:
    row = _get(db, discount_id, company.id)
    code = normalize_code(payload.code)
    if not code:
        raise problem(400, "Ingresa un código de descuento.")
    row.code = code
    row.description = payload.description.strip()
    used = redemption_count(db, row.id)
    if payload.max_redemptions < used:
        raise problem(400, "El máximo de usos no puede ser menor que los ya registrados.")
    row.percent = payload.percent
    row.max_discount = payload.max_discount
    row.max_redemptions = payload.max_redemptions
    row.expires_at = payload.expires_at
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Ya existe un código con ese nombre.") from None
    db.refresh(row)
    return _out(row, db=db)


@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discount_code(
    discount_id: int, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> None:
    row = _get(db, discount_id, company.id)
    db.delete(row)
    db.commit()

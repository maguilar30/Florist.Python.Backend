from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError

from app.delivery import list_delivery_fees, unique_code
from app.deps import AdminUser, CurrentCompany, DbSession
from app.errors import problem
from app.models.delivery_fee import DeliveryFee
from app.schemas.delivery import DeliveryFeeOut, DeliveryFeeUpdate
from app.seed import ensure_delivery_fees

router = APIRouter(prefix="/delivery-fees", tags=["delivery"])


def _out(row: DeliveryFee) -> DeliveryFeeOut:
    return DeliveryFeeOut(
        id=row.id,
        code=row.code,
        label=row.label,
        fee=float(row.fee),
        requires_address=row.requires_address,
        sort_order=row.sort_order,
    )


@router.get("", response_model=list[DeliveryFeeOut])
def get_delivery_fees(db: DbSession, company: CurrentCompany) -> list[DeliveryFeeOut]:
    ensure_delivery_fees(db, company)
    return [_out(row) for row in list_delivery_fees(db, company.id)]


@router.put("", response_model=list[DeliveryFeeOut])
def update_delivery_fees(
    payload: DeliveryFeeUpdate, _admin: AdminUser, db: DbSession, company: CurrentCompany
) -> list[DeliveryFeeOut]:
    existing = {row.id: row for row in list_delivery_fees(db, company.id)}
    keep_ids: set[int] = set()
    creations: list[tuple[int, object]] = []
    for index, item in enumerate(payload.options, start=1):
        label = item.label.strip()
        if item.id:
            row = existing.get(item.id)
            if row is None or row.company_id != company.id:
                raise problem(404, "Not found", "Delivery option not found.")
            row.label = label
            row.fee = item.fee
            row.requires_address = item.requires_address
            row.sort_order = index
            keep_ids.add(row.id)
        else:
            creations.append((index, item))

    for row_id, row in existing.items():
        if row_id not in keep_ids:
            db.delete(row)
    db.flush()

    reserved = {row.code for row in list_delivery_fees(db, company.id)}
    for index, item in creations:
        label = item.label.strip()
        code = unique_code(db, company.id, label, reserved)
        reserved.add(code)
        db.add(
            DeliveryFee(
                company_id=company.id,
                code=code,
                label=label,
                fee=item.fee,
                requires_address=item.requires_address,
                sort_order=index,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise problem(409, "Conflict", "A delivery option with this name already exists.") from None
    return [_out(row) for row in list_delivery_fees(db, company.id)]

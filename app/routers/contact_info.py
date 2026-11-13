from fastapi import APIRouter

from app.deps import AdminUser, CurrentCompany, DbSession
from app.models.company_contact import CompanyContact
from app.schemas.contact_info import ContactInfoOut, ContactInfoUpdate
from app.seed import ensure_company_contact

router = APIRouter(prefix="/contact-info", tags=["contact-info"])


def _out(row: CompanyContact) -> ContactInfoOut:
    return ContactInfoOut(
        heading=row.heading,
        description=row.description,
        address=row.address,
        phone=row.phone,
        hours=row.hours,
        email=row.email,
        instagram_url=row.instagram_url,
        facebook_url=row.facebook_url,
        whatsapp_url=row.whatsapp_url,
    )


def _clean(value: str) -> str:
    return value.strip()


@router.get("", response_model=ContactInfoOut)
def get_contact_info(db: DbSession, company: CurrentCompany) -> ContactInfoOut:
    return _out(ensure_company_contact(db, company))


@router.put("", response_model=ContactInfoOut)
def update_contact_info(
    payload: ContactInfoUpdate,
    _admin: AdminUser,
    db: DbSession,
    company: CurrentCompany,
) -> ContactInfoOut:
    row = ensure_company_contact(db, company)
    row.heading = _clean(payload.heading)
    row.description = _clean(payload.description)
    row.address = _clean(payload.address)
    row.phone = _clean(payload.phone)
    row.hours = _clean(payload.hours)
    row.email = _clean(payload.email).lower()
    row.instagram_url = _clean(payload.instagram_url)
    row.facebook_url = _clean(payload.facebook_url)
    row.whatsapp_url = _clean(payload.whatsapp_url)
    db.commit()
    db.refresh(row)
    return _out(row)

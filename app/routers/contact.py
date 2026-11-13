from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import case, select

from app.deps import AdminUser, DbSession
from app.errors import problem
from app.mail import send_contact_message_email
from app.models.contact_message import ContactMessage
from app.schemas.contact import (
    ContactMessageCreate,
    ContactMessageOut,
    ContactMessageResponse,
    ContactMessageUpdate,
)

router = APIRouter(prefix="/contact-messages", tags=["contact"])

SUCCESS_MESSAGE = "Gracias por escribirnos. Te contactaremos pronto."


def _out(row: ContactMessage) -> ContactMessageOut:
    return ContactMessageOut(
        id=row.id,
        name=row.name,
        email=row.email,
        message=row.message,
        read_at=row.read_at,
        created_at=row.created_at,
    )


def _get_message(db: DbSession, message_id: int) -> ContactMessage:
    row = db.get(ContactMessage, message_id)
    if row is None:
        raise problem(404, "Not found", "Contact message not found.")
    return row


@router.post("", response_model=ContactMessageResponse, status_code=status.HTTP_201_CREATED)
def create_contact_message(payload: ContactMessageCreate, db: DbSession) -> ContactMessageResponse:
    row = ContactMessage(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        message=payload.message.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        send_contact_message_email(name=row.name, email=row.email, body=row.message, message_id=row.id)
    except HTTPException:
        pass

    return ContactMessageResponse(status="ok", message=SUCCESS_MESSAGE, contact_message=_out(row))


@router.get("", response_model=list[ContactMessageOut])
def list_contact_messages(_admin: AdminUser, db: DbSession) -> list[ContactMessageOut]:
    rows = db.scalars(
        select(ContactMessage).order_by(
            case((ContactMessage.read_at.is_(None), 0), else_=1),
            ContactMessage.created_at.desc(),
            ContactMessage.id.desc(),
        )
    )
    return [_out(row) for row in rows]


@router.get("/{message_id}", response_model=ContactMessageOut)
def get_contact_message(message_id: int, _admin: AdminUser, db: DbSession) -> ContactMessageOut:
    return _out(_get_message(db, message_id))


@router.patch("/{message_id}", response_model=ContactMessageOut)
def update_contact_message(
    message_id: int,
    payload: ContactMessageUpdate,
    _admin: AdminUser,
    db: DbSession,
) -> ContactMessageOut:
    row = _get_message(db, message_id)
    if payload.read is True:
        row.read_at = datetime.now(UTC)
    elif payload.read is False:
        row.read_at = None
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_message(message_id: int, _admin: AdminUser, db: DbSession) -> None:
    row = _get_message(db, message_id)
    db.delete(row)
    db.commit()

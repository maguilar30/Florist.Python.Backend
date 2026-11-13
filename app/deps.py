from typing import Annotated

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import problem
from app.models.company import Company
from app.models.user import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_company(
    db: DbSession,
    x_company_id: Annotated[str | None, Header()] = None,
) -> Company:
    slug = (x_company_id or "").strip().lower()
    if not slug:
        raise problem(400, "Company required", "The X-Company-Id header is required.")
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise problem(404, "Unknown company", "The company identifier is not valid.")
    return company


def _user_from_credentials(
    db: Session,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    required: bool,
) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        if required:
            raise problem(401, "Unauthorized", "A valid bearer token is required.")
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        if required:
            raise problem(401, "Unauthorized", "The access token has expired.") from None
        return None
    except jwt.InvalidTokenError:
        if required:
            raise problem(401, "Unauthorized", "The access token is invalid.") from None
        return None

    user_id = payload.get("sub")
    user = db.get(User, user_id) if user_id else None
    if user is None and required:
        raise problem(401, "Unauthorized", "The user no longer exists.")
    return user


def _ensure_user_company(
    user: User,
    company: Company,
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    if user.company_id != company.id:
        raise problem(403, "Forbidden", "This account does not belong to this company.")
    if credentials is None:
        return
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        return
    token_company = payload.get("company_id")
    if token_company and token_company != company.id:
        raise problem(403, "Forbidden", "This account does not belong to this company.")


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    company: Annotated[Company, Depends(get_current_company)],
) -> User:
    user = _user_from_credentials(db, credentials, required=True)
    assert user is not None
    _ensure_user_company(user, company, credentials)
    return user


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    company: Annotated[Company, Depends(get_current_company)],
) -> User | None:
    user = _user_from_credentials(db, credentials, required=False)
    if user is None:
        return None
    _ensure_user_company(user, company, credentials)
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role.lower() != "admin":
        raise problem(403, "Forbidden", "Administrator access is required.")
    return user


CurrentCompany = Annotated[Company, Depends(get_current_company)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]

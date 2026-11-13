from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import problem
from app.models.user import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


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


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    user = _user_from_credentials(db, credentials, required=True)
    assert user is not None
    return user


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    return _user_from_credentials(db, credentials, required=False)


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role.lower() != "admin":
        raise problem(403, "Forbidden", "Administrator access is required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]

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


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise problem(401, "Unauthorized", "A valid bearer token is required.")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise problem(401, "Unauthorized", "The access token has expired.") from None
    except jwt.InvalidTokenError:
        raise problem(401, "Unauthorized", "The access token is invalid.") from None

    user_id = payload.get("sub")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise problem(401, "Unauthorized", "The user no longer exists.")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role.lower() != "admin":
        raise problem(403, "Forbidden", "Administrator access is required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]

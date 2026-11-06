"""Password hashing, JWT and role checks."""
import base64
import hashlib
import hmac
import os
import uuid
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, utcnow
from .models import User

ROLE_RANK = {"viewer": 0, "analyst": 1, "approver": 2, "admin": 3}
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        candidate = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), **_SCRYPT)
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except ValueError:
        return False


# Compared against when the email is unknown, so response time does not reveal which emails exist.
DUMMY_HASH = hash_password(os.urandom(16).hex())


def create_token(user: User) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user.id),
        "tid": str(user.tenant_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    denied = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", {"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise denied
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise denied from None
    # Role is read from the database on every request, so a role change applies immediately.
    user = db.get(User, user_id)
    if user is None:
        raise denied
    return user


def has_role(user: User, role: str) -> bool:
    return ROLE_RANK[user.role] >= ROLE_RANK[role]


def require_role(role: str):
    def checker(user: User = Depends(current_user)) -> User:
        if not has_role(user, role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {role} role or higher")
        return user

    return checker

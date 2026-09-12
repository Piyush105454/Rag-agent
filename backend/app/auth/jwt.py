"""
app/auth/jwt.py

JWT creation and verification helpers for the RAG backend.

Uses python-jose (jose library) with HS256 signing by default.
The JWT payload follows the structure defined in app.auth.models.TokenData.

Public API:
  create_access_token(user_id, groups) -> str
      Mint a signed JWT for the given user.

  decode_token(token) -> TokenData
      Verify signature + expiry and return the decoded payload.

  verify_token(token) -> User
      decode_token wrapper that returns a User principal object.
      Raises HTTP 401 on any failure so callers do not need try/except.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.auth.models import TokenData, User
from app.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM = settings.jwt_algorithm
_SECRET = settings.jwt_secret
_EXPIRE_MINUTES = settings.jwt_expire_minutes


def create_access_token(user_id: str, groups: List[str]) -> str:
    """
    Create and sign a JWT for the given user.

    Parameters
    ----------
    user_id:
        Stable user identifier stored in the ``sub`` claim.
    groups:
        List of access-group strings to embed in the token.

    Returns
    -------
    str
        Compact serialised JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_EXPIRE_MINUTES)

    payload: dict = {
        "sub": user_id,
        "groups": groups,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token: str = jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)
    logger.debug("Issued JWT for user_id=%s exp=%s", user_id, expire.isoformat())
    return token


def decode_token(token: str) -> TokenData:
    """
    Verify and decode a JWT string.

    Raises
    ------
    HTTPException (401)
        If the token is malformed, has an invalid signature, or has expired.

    Returns
    -------
    TokenData
        Validated payload extracted from the token.
    """
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub: str | None = payload.get("sub")
    groups: List[str] = payload.get("groups", [])
    exp: int | None = payload.get("exp")

    if sub is None or exp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate group list type defensively
    if not isinstance(groups, list):
        groups = [str(groups)]

    return TokenData(sub=sub, groups=groups, exp=exp)


def verify_token(token: str) -> User:
    """
    High-level helper that decodes a token and returns a User principal.

    This is the function used by the FastAPI dependency in app.api.deps.

    Raises
    ------
    HTTPException (401)
        Propagated from decode_token on any failure.

    Returns
    -------
    User
        Authenticated user principal ready for injection into route handlers.
    """
    token_data = decode_token(token)
    return User(user_id=token_data.sub, groups=token_data.groups)

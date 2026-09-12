"""
deps.py -- FastAPI dependency injectors for authentication.

get_current_user() decodes the Bearer JWT from the Authorization header,
validates it against settings.JWT_SECRET_KEY, and returns the decoded payload.
Raises HTTP 401 on any failure.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """
    Validate the JWT Bearer token and return the decoded payload.

    Payload must contain 'sub' (user ID) and 'groups' (list of access groups).

    Returns:
        Decoded JWT payload dict (includes sub, groups, exp, etc.)

    Raises:
        HTTPException 401: On missing, expired, or invalid token.
    """
    token = credentials.credentials
    try:
        import jwt as pyjwt
        from app.core.config import settings  # type: ignore[import]

        payload: dict = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        if "sub" not in payload:
            raise ValueError("Token missing 'sub' claim")
        if not isinstance(payload.get("groups", []), list):
            raise ValueError("Token 'groups' claim must be a list")

        return payload

    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

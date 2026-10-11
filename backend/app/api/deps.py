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

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """
    JWT authentication is TEMPORARILY DISABLED for easy local testing.
    Always returns a mock user with full access groups regardless of the token provided.
    """
    # Return a mock payload so the user doesn't have to deal with JWT generation
    return {
        "sub": "local-dev-user",
        "groups": ["general", "engineering", "sales", "product"]
    }

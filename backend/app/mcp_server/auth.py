"""
auth.py -- JWT verification for the MCP server.

Reuses the same token validation logic as the REST API so access-control
is consistent across both interfaces.  Raises mcp.server.fastmcp.exceptions.ToolError
(or a compatible exception) on invalid/expired tokens so the MCP framework
returns a structured error to the calling client.
"""

from __future__ import annotations

from typing import Any


class User:
    """Minimal user representation extracted from a verified JWT."""

    def __init__(self, user_id: str, groups: list[str], raw: dict) -> None:
        self.user_id = user_id
        self.groups = groups
        self.raw = raw  # full decoded payload


def verify_mcp_auth(token: str) -> User:
    """
    Decode and validate a Bearer JWT token for MCP tool calls.

    Uses the same SECRET_KEY and algorithm as the REST API deps module.
    Raises ToolError on any validation failure so the MCP framework returns
    a clean error to the client without leaking internal details.

    Args:
        token: Raw JWT string (without "Bearer " prefix).

    Returns:
        Populated User object with user_id and groups.

    Raises:
        ToolError: On expired token, invalid signature, missing claims, etc.
    """
    try:
        from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[import]
    except ImportError:
        # Fallback if the import path differs between MCP SDK versions
        class ToolError(Exception):  # type: ignore[no-redef]
            pass

    try:
        import jwt as pyjwt  # type: ignore[import]
        from app.core.config import settings  # type: ignore[import]

        payload: dict = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        user_id: str = payload.get("sub", "")
        groups: list = payload.get("groups", [])

        if not user_id:
            raise ToolError("JWT is missing required 'sub' claim.")
        if not isinstance(groups, list):
            raise ToolError("JWT 'groups' claim must be a list.")

        return User(user_id=user_id, groups=groups, raw=payload)

    except ToolError:
        raise
    except pyjwt.ExpiredSignatureError as exc:
        raise ToolError("JWT token has expired.") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ToolError(f"Invalid JWT token: {exc}") from exc
    except Exception as exc:
        raise ToolError(f"Authentication error: {exc}") from exc

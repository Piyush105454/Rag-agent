"""
app/auth/models.py

Pydantic models for authentication and authorisation in the RAG backend.

Three models are defined:
  - TokenData  : the decoded payload stored inside a JWT (internal use)
  - User       : the principal object propagated through request context
  - Token      : the API response returned after successful authentication

Groups are always a List[str] — users may belong to zero or more access
groups.  No group names are hardcoded; they are purely runtime strings
carried in the JWT and matched against per-document access_group values
in the database.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class TokenData(BaseModel):
    """
    Decoded JWT payload.

    `sub` holds the stable user identifier (UUID string).
    `groups` is the list of access groups the user belongs to.
    `exp` is the UNIX timestamp at which the token expires.
    """

    sub: str = Field(..., description="Subject — the user's unique identifier (UUID).")
    groups: List[str] = Field(
        default_factory=list,
        description="Access groups the user belongs to. Matched against document access_group.",
    )
    exp: int = Field(..., description="Token expiry as a UNIX timestamp.")


class User(BaseModel):
    """
    Authenticated principal, extracted from the JWT and injected into every
    protected route via the ``get_current_user`` dependency.

    `user_id` corresponds to the ``sub`` claim in the JWT.
    `groups` is propagated unchanged from the token.
    """

    user_id: str = Field(..., description="Stable user identifier (UUID string).")
    groups: List[str] = Field(
        default_factory=list,
        description="Access groups this user belongs to.",
    )


class Token(BaseModel):
    """
    Response body returned by the /auth/token endpoint after a successful
    login or token refresh.
    """

    access_token: str = Field(..., description="Signed JWT string.")
    token_type: str = Field(default="bearer", description="OAuth2 token type.")

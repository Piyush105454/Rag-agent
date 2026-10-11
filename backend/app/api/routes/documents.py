"""
documents.py -- GET /documents endpoint.

Returns the list of indexed documents visible to the requesting user's
access groups.  Requires a valid JWT -- access groups are read from the
token, not from request parameters, so users cannot enumerate documents
outside their entitlements.
"""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user  # type: ignore[import]

router = APIRouter(tags=["documents"])


@router.get("/documents", summary="List documents visible to the current user")
async def list_documents(
    current_user: dict = Depends(get_current_user),
) -> List[dict[str, Any]]:
    """
    Return all documents the authenticated user is allowed to see.

    Access groups are taken exclusively from the verified JWT -- they are
    never accepted as query parameters to prevent privilege escalation.

    Returns:
        List of document dicts sorted by indexed_at descending:
          file_name, access_group, indexed_at, chunk_count, source
    """
    user_groups: List[str] = current_user.get("groups", [])

    if not user_groups:
        return []

    try:
        from app.vector_store.pgvector_store import get_vector_store  # type: ignore[import]
        store = await get_vector_store()
        docs = await store.get_documents_by_groups(user_groups)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to query document store: {exc}",
        ) from exc

    # Sort by indexed_at descending (most recently indexed first)
    docs.sort(
        key=lambda d: d.get("indexed_at") or "",
        reverse=True,
    )

    return docs

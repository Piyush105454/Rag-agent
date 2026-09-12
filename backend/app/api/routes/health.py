"""
health.py -- GET /health endpoint.

Returns system readiness: database connectivity, embedding model status,
and current server timestamp.  Designed for load balancer health checks
and uptime monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="System health check")
async def health_check() -> dict[str, Any]:
    """
    Return current health status of the system.

    Checks:
      - Database: execute SELECT 1 via the async session
      - Embed model: check the embedding model singleton is loaded

    Returns:
        JSON with status, db, embed_model, and timestamp fields.
    """
    db_status = "connected"
    embed_status = "loaded"

    # Database connectivity check
    try:
        from app.db.session import get_async_session  # type: ignore[import]
        from sqlalchemy import text

        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    # Embedding model check
    try:
        from app.db.vector_store import get_vector_store  # type: ignore[import]
        store = get_vector_store()
        # Accessing the model attribute confirms it was loaded
        _ = store.embedding_model
    except Exception as exc:
        embed_status = f"error: {exc}"

    overall = "ok" if db_status == "connected" and embed_status == "loaded" else "degraded"

    return {
        "status": overall,
        "db": db_status,
        "embed_model": embed_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

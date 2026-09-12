"""
query_logger.py -- Async query logging: persists every RAG request/response
to the database for auditing, quality monitoring, and per-user history.

Design principles:
  - Never raises: all DB errors are caught and written to stderr only, so a
    logging failure never breaks the user-facing request.
  - Uses the shared async DB session from app.db.session.
  - Provides get_user_logs() for the user's own history (never cross-user).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, List

logger = logging.getLogger(__name__)


async def log_query(
    user_id: str,
    user_groups: List[str],
    question: str,
    result: Any,            # AgentState dict
    latency_ms: int,
) -> None:
    """
    Persist a query log row to the database.

    Never raises -- any exception is swallowed and printed to stderr so that
    logging failures are silent to the end user.

    Args:
        user_id:     Authenticated user UUID.
        user_groups: User's access groups at query time.
        question:    Original (pre-rewrite) question from the user.
        result:      Final AgentState returned by run_rag().
        latency_ms:  Total time from API handler entry to first byte, in ms.
    """
    try:
        from app.db.session import get_async_session  # type: ignore[import]
        from app.db.models import QueryLog              # type: ignore[import]
        from sqlalchemy import insert

        row = {
            "user_id": user_id,
            "user_groups": json.dumps(user_groups),
            "question": question,
            "rewritten_query": result.get("rewritten_query"),
            "answer": result.get("answer"),
            "sources": json.dumps(result.get("sources", [])),
            "confidence": result.get("confidence", 0.0),
            "is_low_confidence": result.get("is_low_confidence", False),
            "latency_ms": latency_ms,
            "error": result.get("error"),
            "created_at": datetime.now(timezone.utc),
        }

        async with get_async_session() as session:
            await session.execute(insert(QueryLog).values(**row))
            await session.commit()

    except Exception as exc:  # noqa: BLE001
        print(
            f"[query_logger] Failed to log query for user {user_id}: {exc}",
            file=sys.stderr,
        )


async def get_user_logs(
    user_id: str,
    limit: int = 50,
) -> List[dict]:
    """
    Return the most recent query logs for a specific user.

    Only returns logs belonging to user_id -- never exposes another user's history.

    Args:
        user_id: Authenticated user UUID.
        limit:   Maximum number of rows to return (default 50).

    Returns:
        List of log dicts ordered by created_at descending.
    """
    try:
        from app.db.session import get_async_session  # type: ignore[import]
        from app.db.models import QueryLog              # type: ignore[import]
        from sqlalchemy import select, desc

        async with get_async_session() as session:
            stmt = (
                select(QueryLog)
                .where(QueryLog.user_id == user_id)
                .order_by(desc(QueryLog.created_at))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": str(row.id),
                    "question": row.question,
                    "rewritten_query": row.rewritten_query,
                    "answer": row.answer,
                    "sources": json.loads(row.sources) if row.sources else [],
                    "confidence": row.confidence,
                    "is_low_confidence": row.is_low_confidence,
                    "latency_ms": row.latency_ms,
                    "error": row.error,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
    except Exception as exc:  # noqa: BLE001
        print(
            f"[query_logger] Failed to fetch logs for user {user_id}: {exc}",
            file=sys.stderr,
        )
        return []

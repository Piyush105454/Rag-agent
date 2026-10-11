"""
tools.py -- MCP tool implementations.

Two tools are exposed:
  query_company_docs       -- RAG query (answer + sources + confidence)
  list_available_documents -- enumerate documents visible to the caller

Both tools verify the caller's JWT before executing, using the same auth
logic as the REST API.  Retrieval/generation logic is delegated entirely to
the shared orchestrator (run_rag) and vector store -- no duplication.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def query_company_docs(question: str, token: str) -> dict:
    """
    Query the company knowledge base and return an AI-generated answer.

    Verifies the caller's JWT, extracts user_id and groups, runs the full
    RAG pipeline, and returns the result as a plain dict.

    Args:
        question: Natural-language question to answer.
        token:    Bearer JWT token string (without "Bearer " prefix).

    Returns:
        dict with keys: answer (str), sources (list), confidence (float).

    Raises:
        ToolError: On authentication failure or pipeline error.
    """
    from app.mcp_server.auth import verify_mcp_auth
    from app.orchestrator.graph import run_rag

    user = verify_mcp_auth(token)

    try:
        state = await run_rag(
            question=question,
            user_id=user.user_id,
            user_groups=user.groups,
        )
    except Exception as exc:
        logger.error("query_company_docs: run_rag failed: %s", exc)
        try:
            from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[import]
        except ImportError:
            class ToolError(Exception): pass  # type: ignore[no-redef]
        raise ToolError(f"RAG pipeline error: {exc}") from exc

    return {
        "answer": state.get("answer") or "",
        "sources": state.get("sources", []),
        "confidence": state.get("confidence", 0.0),
    }


async def list_available_documents(token: str) -> list:
    """
    List documents accessible to the authenticated user.

    Verifies the caller's JWT, reads their access groups, and delegates to
    the vector store's get_documents_by_groups() method.

    Args:
        token: Bearer JWT token string (without "Bearer " prefix).

    Returns:
        List of dicts: [{file, access_group, updated_at}]

    Raises:
        ToolError: On authentication or store lookup failure.
    """
    from app.mcp_server.auth import verify_mcp_auth

    user = verify_mcp_auth(token)

    try:
        from app.vector_store.pgvector_store import get_vector_store  # type: ignore[import]
        store = await get_vector_store()
        docs = await store.get_documents_by_groups(user.groups)
    except Exception as exc:
        logger.error("list_available_documents: store lookup failed: %s", exc)
        try:
            from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[import]
        except ImportError:
            class ToolError(Exception): pass  # type: ignore[no-redef]
        raise ToolError(f"Document store error: {exc}") from exc

    return [
        {
            "file": d.get("file_name", ""),
            "access_group": d.get("access_group", ""),
            "updated_at": d.get("indexed_at", ""),
        }
        for d in docs
    ]

"""
server.py -- FastMCP server entry point.

Wraps the two MCP tools (query_company_docs, list_available_documents) and
exposes them over SSE/HTTP so any MCP-compatible client (Claude Desktop,
Claude Code, other agents) can install this as a remote plugin.

Run with:
    python -m app.mcp_server.server
or via the docker-compose service definition.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP  # type: ignore[import]

from app.mcp_server import tools as _tools

# ── Server instance ───────────────────────────────────────────────────────

mcp = FastMCP(
    name="Company Knowledge Assistant",
    description=(
        "Query internal company documents and list available document sources. "
        "All access is governed by JWT-based group permissions."
    ),
)

# ── Tool registration ─────────────────────────────────────────────────────

@mcp.tool(
    name="query_company_docs",
    description=(
        "Ask a question against the company's indexed document knowledge base. "
        "Returns an AI-generated answer grounded in the retrieved documents, "
        "along with source citations and a confidence score. "
        "Requires a valid JWT in the `token` argument."
    ),
)
async def query_company_docs(question: str, token: str) -> dict:
    """Delegate to the shared tool implementation."""
    return await _tools.query_company_docs(question, token)


@mcp.tool(
    name="list_available_documents",
    description=(
        "List all documents the authenticated user is permitted to access. "
        "Returns file names, access groups, and last-indexed timestamps. "
        "Requires a valid JWT in the `token` argument."
    ),
)
async def list_available_documents(token: str) -> list:
    """Delegate to the shared tool implementation."""
    return await _tools.list_available_documents(token)


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from app.core.config import settings  # type: ignore[import]

    mcp.run(
        transport="sse",
        host=getattr(settings, "MCP_HOST", "0.0.0.0"),
        port=int(getattr(settings, "MCP_PORT", 8001)),
    )

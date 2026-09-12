"""
retriever.py -- LangGraph node: embeds the (rewritten) query and retrieves
the top-k most similar chunks from the pgvector store, filtered by the
user's access groups.

Depends on the singleton VectorStore exposed by app.db.vector_store.
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.state import AgentState

logger = logging.getLogger(__name__)


async def run(state: AgentState) -> AgentState:
    """
    LangGraph node: vector-store retriever.

    Reads:  state["rewritten_query"] (falls back to state["question"])
            state["user_groups"]
    Writes: state["retrieved_chunks"]

    Args:
        state: Current AgentState from the graph.

    Returns:
        Updated AgentState with retrieved_chunks populated.
    """
    # Late import to avoid circular imports and allow lazy DB initialisation
    from app.db.vector_store import get_vector_store  # type: ignore[import]

    query: str = state.get("rewritten_query") or state["question"]
    user_groups: list = state["user_groups"]

    try:
        store = get_vector_store()
        chunks = await store.similarity_search(
            query=query,
            user_groups=user_groups,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("retriever: similarity_search failed: %s", exc)
        chunks = []

    logger.debug("retriever: got %d chunks for query=%r", len(chunks), query)
    return {**state, "retrieved_chunks": chunks}

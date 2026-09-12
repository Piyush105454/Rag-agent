"""
graph.py -- Builds and compiles the LangGraph StateGraph that orchestrates
the full RAG pipeline.

Graph topology:
  rewrite -> retrieve -> rerank -> guard --[low confidence]--> END
                                         --[ok]-------------> generate -> END

Exports:
  rag_graph  -- compiled LangGraph graph (invoke / astream compatible)
  run_rag()  -- async convenience wrapper returning the final AgentState
"""

from __future__ import annotations

import logging
from typing import List

from langgraph.graph import END, StateGraph  # type: ignore[import]

from app.orchestrator.nodes import (
    confidence_guard,
    generator,
    query_rewriter,
    reranker,
    retriever,
)
from app.orchestrator.state import AgentState, initial_state

logger = logging.getLogger(__name__)

# ── Routing function ──────────────────────────────────────────────────────

def _route_after_guard(state: AgentState) -> str:
    """
    Conditional edge: after the confidence guard, decide whether to generate
    an answer or short-circuit to END (low confidence path already has an answer).
    """
    if state.get("is_low_confidence"):
        return END
    return "generate"


# ── Graph builder ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct, configure, and compile the LangGraph StateGraph.

    Returns:
        A compiled StateGraph ready to invoke.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("rewrite", query_rewriter.run)
    graph.add_node("retrieve", retriever.run)
    graph.add_node("rerank", reranker.run)
    graph.add_node("guard", confidence_guard.run)
    graph.add_node("generate", generator.run)

    # Entry point
    graph.set_entry_point("rewrite")

    # Linear edges
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "guard")

    # Conditional branch after confidence guard
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {END: END, "generate": "generate"},
    )

    graph.add_edge("generate", END)

    return graph.compile()


# Singleton compiled graph
rag_graph = build_graph()


# ── Public convenience wrapper ────────────────────────────────────────────

async def run_rag(
    question: str,
    user_id: str,
    user_groups: List[str],
) -> AgentState:
    """
    Run the full RAG pipeline and return the final AgentState.

    For non-streaming callers (MCP tools, evaluation scripts) this will also
    drain the token generator so state["answer"] is fully populated.

    Args:
        question:    User question string.
        user_id:     Authenticated user UUID.
        user_groups: List of access-group strings from the JWT.

    Returns:
        Final AgentState after all nodes have executed.
    """
    state = initial_state(question, user_id, user_groups)
    result: AgentState = await rag_graph.ainvoke(state)

    # Drain generator if the generate node ran (non-streaming path)
    if result.get("_token_generator") is not None and result.get("answer") is None:
        answer = await generator.drain_generator(result)
        result = {**result, "answer": answer}

    return result

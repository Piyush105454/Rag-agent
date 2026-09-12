"""
query_rewriter.py -- LangGraph node: rewrites the user question into a
clearer, more retrieval-friendly query using the LLM.

Failure is handled gracefully: if the LLM call fails or returns an empty /
identical string, the original question is used as the fallback so the
pipeline always continues.
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.llm_factory import get_llm_client
from app.orchestrator.prompts import build_query_rewrite_messages, QUERY_REWRITE_SYSTEM
from app.orchestrator.state import AgentState

logger = logging.getLogger(__name__)


async def run(state: AgentState) -> AgentState:
    """
    LangGraph node: query rewriter.

    Reads:  state["question"]
    Writes: state["rewritten_query"]

    Args:
        state: Current AgentState from the graph.

    Returns:
        Updated AgentState with rewritten_query populated.
    """
    question: str = state["question"]

    try:
        llm = get_llm_client()
        messages = build_query_rewrite_messages(question)
        rewritten: str = await llm.complete(messages, system=QUERY_REWRITE_SYSTEM)
        rewritten = rewritten.strip()

        # Sanity checks: reject empty output or trivial rephrasings
        if not rewritten or rewritten.lower() == question.lower():
            logger.debug(
                "query_rewriter: LLM returned identical/empty text; "
                "using original question as rewritten_query"
            )
            rewritten = question

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "query_rewriter: LLM call failed (%s); "
            "falling back to original question",
            exc,
        )
        rewritten = question

    return {**state, "rewritten_query": rewritten}

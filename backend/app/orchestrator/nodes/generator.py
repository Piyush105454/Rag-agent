"""
generator.py -- LangGraph node: calls the LLM to generate the final answer.

Builds the system prompt (with user_groups injected) and user prompt (with
reranked chunks as context), streams tokens from the LLM, accumulates the
full answer text, extracts source metadata from reranked_chunks, and stores
both the accumulated answer and the async token generator in state.

The API layer reads state["_token_generator"] to forward tokens to the SSE
response without re-running the LLM.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, List

from app.orchestrator.llm_factory import get_llm_client
from app.orchestrator.prompts import build_system_prompt, build_user_prompt
from app.orchestrator.state import AgentState

logger = logging.getLogger(__name__)


async def run(state: AgentState) -> AgentState:
    """
    LangGraph node: answer generator.

    Reads:  state["reranked_chunks"], state["user_groups"],
            state["rewritten_query"] / state["question"]
    Writes: state["answer"], state["sources"], state["_token_generator"]

    Args:
        state: Current AgentState from the graph.

    Returns:
        Updated AgentState with answer, sources, and _token_generator set.
    """
    chunks: List[Any] = state.get("reranked_chunks", [])
    user_groups: List[str] = state.get("user_groups", [])
    question: str = state.get("rewritten_query") or state["question"]

    system_prompt = build_system_prompt(user_groups)
    user_prompt = build_user_prompt(question, chunks)
    messages = [{"role": "user", "content": user_prompt}]

    llm = get_llm_client()

    # Build a re-entrant async generator that:
    #   1. Streams tokens to the caller
    #   2. Accumulates the full answer in a mutable container
    accumulated: List[str] = []

    async def token_gen() -> AsyncGenerator[str, None]:
        async for token in llm.stream(messages, system=system_prompt):
            accumulated.append(token)
            yield token

    # Materialise the generator object -- the API layer will iterate it
    gen = token_gen()

    # Extract sources from reranked chunks
    sources: List[dict] = []
    seen_ids: set = set()
    for chunk in chunks:
        if hasattr(chunk, "chunk_id"):
            cid = chunk.chunk_id
            fname = chunk.file_name
            page = chunk.page_number
        else:
            cid = chunk.get("chunk_id", "")
            fname = chunk.get("file_name", "unknown")
            page = chunk.get("page_number", 0)

        if cid not in seen_ids:
            seen_ids.add(cid)
            sources.append({"file": fname, "page": page, "chunk_id": cid})

    # We cannot await the generator here (streaming happens in the API layer).
    # Store it in state for the API to consume; answer will be set after streaming.
    # The API layer MUST call drain_generator(state) to populate state["answer"].
    return {
        **state,
        "answer": None,       # populated after streaming completes
        "sources": sources,
        "_token_generator": gen,
        "_accumulated": accumulated,  # reference shared with the generator closure
    }


async def drain_generator(state: AgentState) -> str:
    """
    Consume the token generator fully and return the accumulated answer.

    Used by the non-streaming code path (e.g., MCP tools, evaluation).
    """
    gen = state.get("_token_generator")
    if gen is None:
        return state.get("answer") or ""
    full = ""
    async for token in gen:
        full += token
    return full

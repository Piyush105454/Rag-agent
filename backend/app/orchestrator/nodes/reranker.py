"""
reranker.py -- LangGraph node: cross-encoder reranking using
BAAI/bge-reranker-base (sentence-transformers CrossEncoder).

Takes the raw retrieved chunks, scores each (query, chunk_text) pair,
sorts descending, selects the top TOP_K_RERANKED, and records the best
score as the pipeline's confidence value.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List

from app.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

TOP_K_RERANKED = int(os.environ.get("TOP_K_RERANKED", "5"))
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-base")

# Lazy singleton so the model is only loaded once per process
_cross_encoder: Any = None


def _get_cross_encoder() -> Any:
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder  # type: ignore[import]
        device = os.environ.get("EMBED_DEVICE", "cpu")
        logger.info("reranker: loading %s on %s", RERANKER_MODEL, device)
        _cross_encoder = CrossEncoder(RERANKER_MODEL, device=device)
    return _cross_encoder


async def run(state: AgentState) -> AgentState:
    """
    LangGraph node: cross-encoder reranker.

    Reads:  state["retrieved_chunks"], state["rewritten_query"] / state["question"]
    Writes: state["reranked_chunks"], state["confidence"]

    Args:
        state: Current AgentState from the graph.

    Returns:
        Updated AgentState with reranked_chunks and confidence set.
    """
    chunks: List[Any] = state.get("retrieved_chunks", [])
    query: str = state.get("rewritten_query") or state["question"]

    if not chunks:
        logger.debug("reranker: no chunks to rerank")
        return {**state, "reranked_chunks": [], "confidence": 0.0}

    try:
        cross_encoder = _get_cross_encoder()

        # Build (query, text) pairs
        pairs = []
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else chunk.get("text", "")
            pairs.append((query, text))

        # Score synchronously (CrossEncoder uses torch internally; wrap if needed)
        import asyncio
        loop = asyncio.get_event_loop()
        scores: List[float] = await loop.run_in_executor(
            None, lambda: cross_encoder.predict(pairs).tolist()
        )

        # Zip and sort descending by score
        scored = sorted(
            zip(scores, chunks), key=lambda x: x[0], reverse=True
        )

        top_k = scored[:TOP_K_RERANKED]
        reranked = [chunk for _, chunk in top_k]
        confidence = float(top_k[0][0]) if top_k else 0.0

    except Exception as exc:  # noqa: BLE001
        logger.error("reranker: scoring failed: %s", exc)
        # Fall back to the original order, truncated
        reranked = chunks[:TOP_K_RERANKED]
        confidence = 0.0

    logger.debug(
        "reranker: top-%d chunks selected, confidence=%.4f",
        len(reranked),
        confidence,
    )
    return {**state, "reranked_chunks": reranked, "confidence": confidence}

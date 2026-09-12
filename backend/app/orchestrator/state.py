"""
state.py -- Defines the shared AgentState TypedDict used across all LangGraph nodes.

This is the single source of truth for data flowing through the graph. Every node
reads from and writes to this state dict. TypedDict provides type-safety at authoring
time while remaining a plain dict at runtime -- compatible with LangGraph state management.
"""

from __future__ import annotations
from typing import Any, List, Optional, TypedDict


class AgentState(TypedDict):
    """
    Central state object passed between every LangGraph node.

    Fields populated progressively as the graph executes:
      query_rewriter   -> rewritten_query
      retriever        -> retrieved_chunks
      reranker         -> reranked_chunks, confidence
      confidence_guard -> is_low_confidence (+ early answer on low confidence)
      generator        -> answer, sources, _token_generator
    """

    # Input
    question: str
    user_id: str
    user_groups: List[str]        # multiple groups supported

    # Query rewriting
    rewritten_query: Optional[str]

    # Retrieval
    retrieved_chunks: List[Any]   # List[SearchResult] from vector store

    # Reranking
    reranked_chunks: List[Any]    # Subset sorted by cross-encoder score
    confidence: float             # Top reranker score; 0.0 if no chunks

    # Confidence guard
    is_low_confidence: bool

    # Generation
    answer: Optional[str]
    sources: List[dict]           # [{"file": ..., "page": ..., "chunk_id": ...}]

    # Streaming handle (internal -- not serialised to client)
    _token_generator: Optional[Any]

    # Error propagation
    error: Optional[str]


def initial_state(
    question: str,
    user_id: str,
    user_groups: List[str],
) -> AgentState:
    """
    Factory that returns a fully-initialised AgentState with safe defaults.

    Args:
        question:    The raw user question as received from the API layer.
        user_id:     Authenticated user UUID (from JWT sub claim).
        user_groups: Access groups the user belongs to (from JWT groups claim).

    Returns:
        An AgentState dict ready to be passed to the LangGraph graph.
    """
    return AgentState(
        question=question,
        user_id=user_id,
        user_groups=user_groups,
        rewritten_query=None,
        retrieved_chunks=[],
        reranked_chunks=[],
        confidence=0.0,
        is_low_confidence=False,
        answer=None,
        sources=[],
        _token_generator=None,
        error=None,
    )

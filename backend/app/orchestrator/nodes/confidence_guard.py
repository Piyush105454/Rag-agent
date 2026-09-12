"""
confidence_guard.py -- LangGraph node: gates the pipeline based on
retrieval confidence.

Compares the top reranker score (state["confidence"]) against
settings.CONFIDENCE_THRESHOLD.  If the score is below threshold the node
short-circuits the pipeline by writing a canned low-confidence answer and
empty sources directly into state -- the graph then routes to END instead
of proceeding to the generator.
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.state import AgentState

logger = logging.getLogger(__name__)

LOW_CONFIDENCE_ANSWER = (
    "The retrieved documents have low confidence for this question. "
    "Please verify directly in the source documents or rephrase your question."
)


def _get_threshold() -> float:
    """Read threshold from settings (lazy import to avoid circular deps)."""
    try:
        from app.core.config import settings  # type: ignore[import]
        return float(settings.CONFIDENCE_THRESHOLD)
    except Exception:
        return 0.3  # safe fallback


async def run(state: AgentState) -> AgentState:
    """
    LangGraph node: confidence guard.

    Reads:  state["confidence"]
    Writes: state["is_low_confidence"]
            state["answer"]  (only on low confidence)
            state["sources"] (only on low confidence, set to [])

    Args:
        state: Current AgentState from the graph.

    Returns:
        Updated AgentState with is_low_confidence flag set.
    """
    confidence: float = state.get("confidence", 0.0)
    threshold: float = _get_threshold()
    is_low = confidence < threshold

    logger.debug(
        "confidence_guard: confidence=%.4f threshold=%.4f is_low=%s",
        confidence,
        threshold,
        is_low,
    )

    update: dict = {**state, "is_low_confidence": is_low}

    if is_low:
        update["answer"] = LOW_CONFIDENCE_ANSWER
        update["sources"] = []
        logger.info(
            "confidence_guard: low confidence (%.4f < %.4f) -- short-circuiting",
            confidence,
            threshold,
        )

    return update

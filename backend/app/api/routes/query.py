"""
query.py -- POST /query SSE streaming endpoint.

Accepts a user question, runs the full RAG pipeline via the LangGraph
orchestrator, and streams the answer token-by-token as Server-Sent Events.

SSE format:
  Each token:    data: {"token": "<text>"}\n\n
  Final event:   data: {"sources": [...], "confidence": 0.87, "done": true}\n\n
  Error event:   data: {"error": "<message>", "done": true}\n\n

JWT is required; user_id and groups are read exclusively from the token.
A fire-and-forget log_query() call persists the result after streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_current_user  # type: ignore[import]

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = None   # ignored; user identity comes from JWT


@router.post("/query", summary="Ask a question against indexed documents (SSE stream)")
async def query(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Run the RAG pipeline and stream the answer as SSE.

    The user_id in the request body is ignored -- identity and group
    membership are always sourced from the verified JWT to prevent spoofing.
    """
    user_id: str = current_user["sub"]
    user_groups: list = current_user.get("groups", [])
    question: str = body.question.strip()

    if not question:
        async def error_stream() -> AsyncGenerator[str, None]:
            yield f'data: {json.dumps({"error": "question must not be empty", "done": True})}\n\n'

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    return StreamingResponse(
        _sse_generator(question, user_id, user_groups),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_generator(
    question: str,
    user_id: str,
    user_groups: list,
) -> AsyncGenerator[str, None]:
    """
    Internal async generator that drives the RAG pipeline and emits SSE events.

    The generator:
      1. Builds the initial state and runs the graph up to (but not including)
         the generator node (i.e., rewrite -> retrieve -> rerank -> guard).
      2. If low confidence, emits the canned answer as a single token + done event.
      3. Otherwise, streams tokens from the generator node's async generator.
      4. Emits the final event with sources + confidence + done=true.
      5. Fire-and-forgets log_query().
    """
    from app.orchestrator.graph import rag_graph
    from app.orchestrator.state import initial_state
    from app.logging_.query_logger import log_query

    start_ms = int(time.monotonic() * 1000)
    state = initial_state(question, user_id, user_groups)
    final_state = state
    answer_text = ""

    try:
        # Run the full graph (the generator node stores the async gen in state)
        final_state = await rag_graph.ainvoke(state)

        if final_state.get("is_low_confidence"):
            # Low-confidence path: answer already set in state by confidence_guard
            answer_text = final_state.get("answer", "")
            yield f'data: {json.dumps({"token": answer_text})}\n\n'

        else:
            # Normal path: stream tokens from the generator
            token_gen = final_state.get("_token_generator")
            if token_gen is not None:
                async for token in token_gen:
                    answer_text += token
                    yield f'data: {json.dumps({"token": token})}\n\n'
            else:
                # Fallback: answer already accumulated (e.g. if graph short-circuited)
                answer_text = final_state.get("answer", "")
                yield f'data: {json.dumps({"token": answer_text})}\n\n'

        # Update answer in final_state for logging
        final_state = {**final_state, "answer": answer_text}

        # Emit final done event
        done_payload = {
            "sources": final_state.get("sources", []),
            "confidence": final_state.get("confidence", 0.0),
            "done": True,
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    except Exception as exc:  # noqa: BLE001
        logger.exception("SSE query handler error for user %s: %s", user_id, exc)
        error_payload = {"error": str(exc), "done": True}
        yield f"data: {json.dumps(error_payload)}\n\n"
        final_state = {**final_state, "error": str(exc)}

    finally:
        # Fire-and-forget: log the query asynchronously
        latency_ms = int(time.monotonic() * 1000) - start_ms
        asyncio.ensure_future(
            log_query(user_id, user_groups, question, final_state, latency_ms)
        )
